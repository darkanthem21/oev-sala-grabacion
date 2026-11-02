from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_POST

from agenda.models import Bloqueo, primera_fecha_pedible
from configuracion.models import Parametros
from personas.models import Area, Rol, Sancion

from . import validacion
from .calendar import construir_calendario_contexto
from .forms import (
    MAXIMO_ACOMPANANTES,
    MAXIMO_PERSONAS,
    AcompananteFormSet,
    FechaReservaForm,
    SeleccionAreaForm,
    SeleccionHorarioForm,
    SolicitudForm,
    primer_error,
)
from .models import Solicitud
from .services import (
    confirmar_solicitud,
    guardar_solicitud_completa,
    obtener_bloques_dia_para_usuario,
    resolver,
    retirar_solicitud,
    revisar_acompanantes,
)
from .wizard import PasoSolicitud, SolicitudWizard

# Los bloqueos que ve el solicitante en el paso 1. El calendario ya no ofrece
# esos bloques; la lista dice por qué faltan. Más que esto ya no es un aviso.
BLOQUEOS_VISIBLES = 8


def es_solicitante(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.SOLICITANTE)


def es_validador(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.VALIDADOR)


def puede_validar(usuario):
    """Decisión del 04/10: el administrador también valida."""
    return usuario.is_authenticated and (usuario.is_staff or usuario.tiene_rol(Rol.VALIDADOR))


def _datos_validacion():
    return {"datos": validacion.cargar()}


@user_passes_test(es_validador, login_url="login_validacion")
def panel_validador(request):
    """Bandeja del validador (US-07)."""
    return render(request, "solicitudes/validador.html", _datos_validacion())


@staff_member_required(login_url="login_gestion")
def panel_validacion_admin(request):
    """La misma bandeja como pestaña del panel del administrador."""
    return render(request, "solicitudes/validacion_admin.html", {**_datos_validacion(), "pestana": "validacion"})


@user_passes_test(puede_validar, login_url="login_validacion")
@require_POST
def resolver_solicitud(request):
    """Aprobar o rechazar desde el panel. Responde JSON al fetch de Alpine: la
    pantalla cambia solo si esto guardó."""
    accion = request.POST.get("accion")
    try:
        solicitud_id = int(request.POST.get("solicitud", ""))
    except ValueError:
        solicitud_id = None
    if solicitud_id is None or accion not in ("aprobar", "rechazar"):
        return JsonResponse({"error": "Pedido inválido. Recarga la página."}, status=400)
    try:
        resolver(solicitud_id, accion == "aprobar", request.POST.get("motivo", ""), request.user,
                 url_base=request.build_absolute_uri("/").rstrip("/"))
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)
    return JsonResponse({"ok": True})


SOLICITUDES_POR_PAGINA = 20
VISTAS_HISTORIAL = ("proximas", "anteriores")


def _contexto_historial(usuario, vista, numero_pagina):
    """Lo que dibuja la tabla del historial: pestaña, página y cuentas."""
    if vista not in VISTAS_HISTORIAL:
        vista = "proximas"

    hoy = timezone.localdate()
    propias = Solicitud.objects.de(usuario)
    proximas, anteriores = propias.proximas(hoy), propias.anteriores(hoy)
    solicitudes = (proximas if vista == "proximas" else anteriores).con_detalle()

    contexto = {
        "pagina": Paginator(solicitudes, SOLICITUDES_POR_PAGINA).get_page(numero_pagina),
        "vista": vista,
        "total_proximas": proximas.count(),
        "total_anteriores": anteriores.count(),
    }
    return contexto


@user_passes_test(es_solicitante, login_url="login_solicitante")
def mis_solicitudes(request):
    """Historial de solicitudes del solicitante con su estado actual (US-09).

    Cada solicitud muestra su área, sus bloques (hora de inicio y término) y la
    fecha. Se listan todas las del usuario conectado, de cualquiera de sus áreas,
    separadas en próximas y anteriores y de a SOLICITUDES_POR_PAGINA por página.
    """
    contexto = _contexto_historial(request.user, request.GET.get("vista"), request.GET.get("pagina"))

    # htmx pide solo la tabla. Al volver con el botón Atrás sin la página en su
    # caché, htmx la pide entera (HX-History-Restore-Request), igual que el
    # navegador sin htmx.
    if request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request"):
        respuesta = render(request, "solicitudes/_tabla_historial.html", contexto)
    else:
        respuesta = render(request, "solicitudes/mis_solicitudes.html", contexto)
    # La misma URL entrega tabla o página según la cabecera: que la caché del
    # navegador no las confunda.
    patch_vary_headers(respuesta, ["HX-Request"])
    return respuesta


@user_passes_test(es_solicitante, login_url="login_solicitante")
@require_POST
def retirar(request, solicitud_id):
    """Retira una solicitud propia que la Oficina todavía no revisa.

    htmx recibe la tabla redibujada en la misma pestaña y página. Sin htmx se
    redirige al historial, para que recargar no reenvíe el formulario.
    """
    if retirar_solicitud(request.user, solicitud_id):
        messages.success(request, f"Retiraste la solicitud #{solicitud_id}. Su horario queda libre.")
    else:
        # Ajena, inexistente o ya revisada: el mismo mensaje para no revelar
        # cuáles existen.
        messages.error(request, f"No se pudo retirar la solicitud #{solicitud_id}: ya no está en revisión.")

    vista, pagina = request.POST.get("vista"), request.POST.get("pagina")
    if request.headers.get("HX-Request"):
        return render(request, "solicitudes/_tabla_historial.html", _contexto_historial(request.user, vista, pagina))
    return redirect(f"{reverse('mis_solicitudes')}?{urlencode({'vista': vista or 'proximas', 'pagina': pagina or 1})}")


@user_passes_test(es_solicitante, login_url="login_solicitante")
def confirmar(request, solicitud_id):
    """US-03: la página del enlace para confirmar asistencia. Es el mismo enlace
    de Mis solicitudes y del correo de aceptación. El GET solo muestra la
    reserva y confirma el POST, para que un lector de correo que abre los
    enlaces no confirme solo."""
    solicitud = get_object_or_404(Solicitud.objects.de(request.user).con_detalle(), pk=solicitud_id)
    if request.method == "POST":
        if confirmar_solicitud(request.user, solicitud_id):
            messages.success(request, f"Confirmaste tu asistencia a la reserva #{solicitud_id}.")
        else:
            messages.error(request, f"La reserva #{solicitud_id} ya no se puede confirmar.")
        return redirect(f"{reverse('mis_solicitudes')}?vista=proximas")
    return render(request, "solicitudes/confirmar.html", {"solicitud": solicitud})


def calendario(request):
    """Vista pública para consultar disponibilidad de la sala en el calendario."""
    fecha_str = request.POST.get("fecha") if request.method == "POST" else request.GET.get("fecha")
    bloques_ids = []
    mensaje_confirmacion = None
    error_confirmacion = None

    if request.method == "POST":
        form = SeleccionHorarioForm(request.POST, usuario=request.user, exigir_todos=False)
        bloques_ids = form.ids_enviados
        if form.is_valid():
            fecha, bloques = form.cleaned_data["fecha"], form.cleaned_data["bloques"]
            mensaje_confirmacion = (
                f"Día seleccionado: {fecha:%d/%m/%Y}. "
                f"Bloque(s) seleccionado(s): {', '.join(b.texto for b in bloques)}."
            )
        else:
            error_confirmacion = primer_error(form)

    ctx = construir_calendario_contexto(request, fecha_str=fecha_str, bloques_seleccionados_ids=bloques_ids)
    ctx.update({
        "mensaje_confirmacion": mensaje_confirmacion,
        "error_confirmacion": error_confirmacion,
    })
    return render(request, "solicitudes/calendario.html", ctx)


def bloques_dia(request):
    """Vista parcial HTMX para consultar y desplegar los bloques de una fecha."""
    fecha_str = request.GET.get("fecha")
    fecha = FechaReservaForm.fecha_de(fecha_str)
    bloques = obtener_bloques_dia_para_usuario(fecha=fecha, usuario=request.user) if fecha else []
    return render(request, "solicitudes/bloques_dia.html", {
        "fecha": fecha,
        "fecha_str": fecha_str,
        "bloques": bloques,
    })


def _sancionado(request):
    """US-10 T2: en vez del formulario, el motivo y desde cuándo puede volver a
    pedir. None si no tiene una sanción vigente. Va antes que el área, porque
    elegir un área no le serviría de nada."""
    sancion = request.user.sancion_vigente
    if sancion is None:
        return None
    return render(request, "solicitudes/sancionado.html", {"sancion": sancion})


@user_passes_test(es_solicitante, login_url="login_solicitante")
def mis_sanciones(request):
    """US-10 T4: las vigentes primero y después las pasadas, siempre del usuario
    conectado. No hay dirección por sanción, así que no hay cómo pedir una ajena."""
    propias = Sancion.objects.filter(usuario=request.user).select_related("levantada_por")
    return render(request, "solicitudes/mis_sanciones.html", {
        "vigentes": propias.vigentes().order_by("-termino", "-id"),
        "pasadas": propias.pasadas(),
    })


@user_passes_test(es_solicitante, login_url="login_solicitante")
def solicitar_area(request):
    """Paso previo de selección de área académica para usuarios con múltiples áreas activas."""
    if respuesta := _sancionado(request):
        return respuesta
    areas = list(request.user.areas.filter(activa=True))
    if not areas:
        return render(request, "solicitudes/sin_area.html")

    wizard = SolicitudWizard(request.session)
    if len(areas) == 1:
        wizard.ajustar_area(areas)
        return redirect(reverse("solicitar"))

    es_cambio = bool(request.GET.get("cambiar"))

    if request.method == "POST":
        form = SeleccionAreaForm(request.POST, usuario=request.user)
        if form.is_valid():
            area_seleccionada = form.cleaned_data["area"]
            wizard.guardar_area(
                area_id=area_seleccionada.id,
                area_nombre=area_seleccionada.nombre,
                reset_horario=es_cambio,
            )
            return redirect(reverse("solicitar"))
    else:
        initial = {}
        if wizard.tiene_area and not es_cambio:
            initial["area"] = wizard.area_id
        form = SeleccionAreaForm(initial=initial, usuario=request.user)

    return render(request, "solicitudes/seleccionar_area.html", {
        "form": form,
        "areas": areas,
        "es_cambio": es_cambio,
    })


@user_passes_test(es_solicitante, login_url="login_solicitante")
def solicitar(request):
    """Flujo multipaso de solicitud de reserva (US-02).

    Paso 1: Selección de horario y bloques en el calendario de disponibilidad.
    Paso 2: Datos de la actividad (motivo y acompañantes).
    Paso 3: Revisión de la reserva, aceptación de términos y confirmación.
    """
    # También corta los POST de cualquier paso: quien está sancionado no avanza.
    if respuesta := _sancionado(request):
        return respuesta
    areas = list(request.user.areas.filter(activa=True))
    if not areas:
        return render(request, "solicitudes/sin_area.html")

    wizard = SolicitudWizard(request.session)
    tiene_multiples_areas = len(areas) > 1

    if tiene_multiples_areas and (request.GET.get("cambiar_area") or request.GET.get("cambiar")):
        wizard.limpiar_horario()
        return redirect(f"{reverse('solicitar_area')}?cambiar=1")

    falta_area = wizard.ajustar_area(areas)
    if falta_area == "elegir":
        return redirect(reverse("solicitar_area"))
    if falta_area == "cambiar":
        return redirect(f"{reverse('solicitar_area')}?cambiar=1")

    paso_param = request.POST.get("paso", request.GET.get("paso"))
    paso_solicitado = PasoSolicitud.resolver(paso_param) if paso_param else PasoSolicitud.HORARIO
    paso_actual = paso_solicitado.validar_acceso(wizard.datos)
    if paso_actual != paso_solicitado and request.method == "GET":
        return redirect(f"{reverse('solicitar')}?paso={paso_actual.value}")

    manejar = {
        PasoSolicitud.HORARIO: _manejar_paso_horario,
        PasoSolicitud.DATOS: _manejar_paso_datos,
        PasoSolicitud.CONFIRMACION: _manejar_paso_confirmacion,
    }[paso_actual]
    return manejar(request, wizard, puede_cambiar_area=tiene_multiples_areas)


@user_passes_test(es_solicitante, login_url="login_solicitante")
def enviada(request, solicitud_id):
    """Confirmación de una solicitud recién enviada, leída de la base."""
    solicitud = get_object_or_404(
        Solicitud.objects.de(request.user).con_detalle().prefetch_related("acompanantes"),
        pk=solicitud_id,
    )
    return render(request, "solicitudes/enviada.html", {"solicitud": solicitud})


def _manejar_paso_horario(request, wizard: SolicitudWizard, puede_cambiar_area: bool = False):
    error_bloques = None

    if request.method == "POST":
        form = SeleccionHorarioForm(request.POST, usuario=request.user)
        if form.is_valid():
            bloques = form.cleaned_data["bloques"]
            wizard.guardar_horario(
                form.cleaned_data["fecha"].isoformat(),
                [b.id for b in bloques],
                ", ".join(b.texto for b in bloques),
            )
            return redirect(f"{reverse('solicitar')}?paso={PasoSolicitud.DATOS.value}")
        error_bloques = primer_error(form)

    contexto = construir_calendario_contexto(
        request,
        fecha_str=wizard.fecha_str,
        bloques_seleccionados_ids=wizard.bloques_ids,
        paso=PasoSolicitud.HORARIO.value,
    )
    contexto.update({
        "paso": PasoSolicitud.HORARIO.value,
        "error_paso": error_bloques,
        "reserva": wizard.obtener_resumen(),
        "puede_cambiar_area": puede_cambiar_area,
        # US-05: la nota del área se lee antes de elegir bloques, no solo al validar.
        "area": Area.objects.filter(pk=wizard.area_id).first(),
        # US-17 AC7: qué no se puede pedir y por qué. Desde la primera fecha
        # pedible, porque lo anterior tampoco se podría pedir sin bloqueo.
        "bloqueos": Bloqueo.objects.vigentes()
                    .filter(hasta__gte=primera_fecha_pedible())
                    .select_related("bloque")[:BLOQUEOS_VISIBLES],
    })
    return render(request, "solicitudes/solicitar.html", contexto)


def _manejar_paso_datos(request, wizard: SolicitudWizard, puede_cambiar_area: bool = False):
    errores_acompanantes = []

    if request.method == "POST":
        form = SolicitudForm(request.POST, usuario=request.user, exigir_terminos=False)
        formset = AcompananteFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            personas_declaradas = form.cleaned_data["personas"]
            esperados = personas_declaradas - 1
            llenos, errores_acompanantes = revisar_acompanantes(
                formset,
                esperados=esperados,
                correo_solicitante=request.user.email,
            )

            if not errores_acompanantes:
                acompanantes_data = [
                    {"nombre": f.cleaned_data["nombre"].strip(), "correo": f.cleaned_data["correo"].strip().lower()}
                    for f in llenos
                ]
                wizard.guardar_datos_actividad(
                    motivo=form.cleaned_data["motivo"].strip(),
                    observaciones=form.cleaned_data.get("observaciones", "").strip(),
                    personas=personas_declaradas,
                    acompanantes=acompanantes_data,
                )
                return redirect(f"{reverse('solicitar')}?paso={PasoSolicitud.CONFIRMACION.value}")
    else:
        initial_form = {
            "motivo": wizard.motivo,
            "observaciones": wizard.observaciones,
            "personas": wizard.personas,
        }
        form = SolicitudForm(initial=initial_form, usuario=request.user, exigir_terminos=False)
        formset = AcompananteFormSet(initial=wizard.acompanantes)

    personas_inicial = wizard.personas
    if form.is_bound and "personas" in form.cleaned_data:
        personas_inicial = form.cleaned_data["personas"]

    contexto = {
        "paso": PasoSolicitud.DATOS.value,
        "form": form,
        "formset": formset,
        "personas_inicial": personas_inicial,
        "maximo_personas": MAXIMO_PERSONAS,
        "maximo_acompanantes": MAXIMO_ACOMPANANTES,
        "reserva": wizard.obtener_resumen(),
        "errores": errores_acompanantes,
        "puede_cambiar_area": puede_cambiar_area,
    }
    return render(request, "solicitudes/solicitar.html", contexto)


def _manejar_paso_confirmacion(request, wizard: SolicitudWizard, puede_cambiar_area: bool = False):
    resumen = wizard.obtener_resumen()
    error_terminos = None
    terminos_texto = Parametros.cargar().terminos

    if request.method == "POST":
        acepta_terminos = bool(request.POST.get("acepta_terminos"))
        if not acepta_terminos:
            error_terminos = "Tienes que aceptar los términos y condiciones para enviar la solicitud."
        else:
            try:
                solicitud_obj = guardar_solicitud_completa(
                    usuario=request.user,
                    datos_reserva=wizard.datos,
                )
            except ValidationError as e:
                error_terminos = "; ".join(e.messages)
            else:
                wizard.limpiar()
                # Redirección y no la página directa: recargar no reenvía el
                # formulario, y la confirmación queda con dirección propia.
                return redirect("solicitud_enviada", solicitud_id=solicitud_obj.id)

    contexto = {
        "paso": PasoSolicitud.CONFIRMACION.value,
        "reserva": resumen,
        "error_terminos": error_terminos,
        "terminos": terminos_texto,
        "puede_cambiar_area": puede_cambiar_area,
    }
    return render(request, "solicitudes/solicitar.html", contexto)
