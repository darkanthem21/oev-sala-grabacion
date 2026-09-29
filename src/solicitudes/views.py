from datetime import datetime
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse

from agenda.models import Bloqueo, primera_fecha_pedible
from configuracion.models import Parametros
from personas.models import Rol

from . import validacion
from .calendar import AgendaCalendar, construir_calendario_contexto
from .forms import (
    MAXIMO_ACOMPANANTES,
    MAXIMO_PERSONAS,
    AcompananteFormSet,
    SeleccionAreaForm,
    SolicitudForm,
)
from .models import Solicitud, SolicitudBloque
from .services import (
    guardar_solicitud_completa,
    obtener_bloques_dia_para_usuario,
    revisar_acompanantes,
)
from .wizard import PasoSolicitud, SolicitudWizard, obtener_limites_reserva


from .wizard import PasoSolicitud, SolicitudWizard, obtener_limites_reserva


def es_solicitante(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.SOLICITANTE)


# Los bloqueos que ve el solicitante en el formulario. Más que esto ya no es un
# aviso sino un calendario, y el calendario es de US-02.
BLOQUEOS_VISIBLES = 8


def _revisar_acompanantes(formset, esperados, correo_solicitante):
    """Cruza las filas llenas con la cantidad de personas declarada.

    Vive fuera de los formularios porque es la unica regla que necesita ver los
    dos a la vez: `personas` esta en uno y las filas en el otro.

    Devuelve (filas_llenas, errores).
    """
    llenos = [f for f in formset.forms if f.esta_lleno]
    errores = []

    if len(llenos) != esperados:
        errores.append(
            f"Declaraste {esperados + 1} personas en sala, así que faltan los datos "
            f"de {esperados} acompañante(s); tienes {len(llenos)} completo(s)."
        )

    # US-02 AC6: si dos filas traen el mismo correo no hay identificacion que
    # valga, y el correo es lo unico que distingue a una persona de otra.
    correos = [f.cleaned_data["correo"].lower() for f in llenos if f.cleaned_data.get("correo")]
    if len(correos) != len(set(correos)):
        errores.append("Hay un correo repetido entre los acompañantes.")
    if correo_solicitante.lower() in correos:
        errores.append("Tu propio correo ya está incluido: eres parte de la cuenta de personas.")

    return llenos, errores


def _estado_inicial(form):
    """Con que valores arranca Alpine al pintar la pagina.

    Se calcula aca y no en la plantilla porque `form.data` es lo que mando el
    navegador, sin limpiar: si alguien reenvia `personas=abc`, interpolarlo tal
    cual en el `x-data` deja el JavaScript de la pagina roto.
    """
    if not form.is_bound:
        return 1, False
    try:
        personas = int(form.data.get("personas", 1))
    except (TypeError, ValueError):
        personas = 1
    return min(max(personas, 1), MAXIMO_PERSONAS), bool(form.data.get("acepta_terminos"))


def _contexto(form, formset, extra=None):
    personas_inicial, acepta_inicial = _estado_inicial(form)
    base = {
        "form": form,
        "formset": formset,
        "personas_inicial": personas_inicial,
        "acepta_inicial": acepta_inicial,
        "maximo_personas": MAXIMO_PERSONAS,
        "maximo_acompanantes": MAXIMO_ACOMPANANTES,
        # US-04 AC5: lo edita el administrador en la pestaña de reglas.
        "terminos": Parametros.cargar().terminos,
        # US-17 AC7: qué no se puede pedir y por qué. Desde la primera fecha
        # pedible, porque lo anterior tampoco se podría pedir sin bloqueo.
        "bloqueos": Bloqueo.objects.vigentes()
                    .filter(hasta__gte=primera_fecha_pedible())
                    .select_related("bloque")[:BLOQUEOS_VISIBLES],
    }
    base.update(extra or {})
    return base


@login_required
def solicitar(request):
    """T4 - formulario de solicitud de reserva (US-02).

    Todavia no escribe nada: cual entidad guarda el estado de la solicitud
    —Solicitud o Ticket— es una decision de modelo que el equipo no ha cerrado.
    Cuando se cierre, lo unico que cambia aca es el bloque de exito.
    """
    areas = request.user.areas.filter(activa=True)
    if not areas.exists():
        # US-05 AC4: la solicitud se vincula a un area. Sin area no hay a que
        # vincularla, y es mejor decirlo que mostrar un desplegable vacio.
        return render(request, "solicitudes/sin_area.html")

    if request.method != "POST":
        form = SolicitudForm(usuario=request.user)
        return render(request, "solicitudes/solicitar.html", _contexto(form, AcompananteFormSet()))

    form = SolicitudForm(request.POST, usuario=request.user)
    formset = AcompananteFormSet(request.POST)

    if not (form.is_valid() and formset.is_valid()):
        return render(request, "solicitudes/solicitar.html", _contexto(form, formset))

    llenos, errores = _revisar_acompanantes(
        formset, form.cleaned_data["personas"] - 1, request.user.email
    )
    if errores:
        return render(request, "solicitudes/solicitar.html", _contexto(form, formset, {"errores": errores}))

    return render(request, "solicitudes/enviada.html", {
        "solicitud": form.cleaned_data,
        "acompanantes": [f.cleaned_data for f in llenos],
    })


# La rama actual conserva la validación del rol de solicitante y la rama entrante
# aporta la lógica de bloqueos visibles para el flujo del form.

def es_validador(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.VALIDADOR)


def es_validador(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.VALIDADOR)


@user_passes_test(es_validador, login_url="login_validacion")
def panel_validador(request):
    """Bandeja del validador, con datos de prueba mientras no exista el modelo.

    `validacion.cargar` es el único punto que sabe de dónde vienen los datos.
    """
    return render(request, "solicitudes/validador.html", {
        "datos": validacion.marcar_bloqueos(validacion.cargar()),
        "origen": validacion.ORIGEN,
    })


def calendario(request):
    """Vista pública para consultar disponibilidad de la sala en el calendario."""
    fecha_str = request.POST.get("fecha") if request.method == "POST" else request.GET.get("fecha")
    bloques_ids = []
    mensaje_confirmacion = None
    error_confirmacion = None

    if request.method == "POST":
        raw_bloques = request.POST.getlist("bloques")
        bloques_ids = [int(b) for b in raw_bloques if b.isdigit()]

        fecha_obj = None
        if fecha_str:
            try:
                fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                fecha_str = None

        fecha_minima, fecha_maxima = obtener_limites_reserva()
        if not fecha_str or not fecha_obj:
            error_confirmacion = "Por favor, selecciona un día del calendario."
        elif fecha_obj < fecha_minima or fecha_obj > fecha_maxima:
            error_confirmacion = "La fecha seleccionada no está dentro del período permitido."
        elif not bloques_ids:
            error_confirmacion = f"Día seleccionado: {fecha_obj.strftime('%d/%m/%Y')}. Por favor, selecciona al menos un bloque disponible."
        else:
            bloques_disponibles = [
                b for b in obtener_bloques_dia_para_usuario(fecha=fecha_obj, usuario=request.user)
                if b.id in bloques_ids and b.disponible
            ]
            if not bloques_disponibles:
                error_confirmacion = "Ninguno de los bloques seleccionados está disponible."
            else:
                horas_texto = ", ".join(b.texto for b in bloques_disponibles)
                mensaje_confirmacion = (
                    f"Día seleccionado: {fecha_obj.strftime('%d/%m/%Y')}. "
                    f"Bloque(s) seleccionado(s): {horas_texto}."
                )

    ctx = construir_calendario_contexto(request, fecha_str=fecha_str, bloques_seleccionados_ids=bloques_ids)
    ctx.update({
        "mensaje_confirmacion": mensaje_confirmacion,
        "error_confirmacion": error_confirmacion,
    })
    return render(request, "solicitudes/calendario.html", ctx)


def bloques_dia(request):
    """Vista parcial HTMX para consultar y desplegar los bloques de una fecha."""
    fecha_str = request.GET.get("fecha")
    fecha = None
    bloques = []
    fecha_valida = True
    fecha_minima, fecha_maxima = obtener_limites_reserva()

    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            if fecha < fecha_minima or fecha > fecha_maxima:
                fecha_valida = False
            else:
                bloques = obtener_bloques_dia_para_usuario(
                    fecha=fecha,
                    usuario=getattr(request, "user", None),
                )
        except ValueError:
            pass

    return render(request, "solicitudes/bloques_dia.html", {
        "fecha": fecha,
        "fecha_str": fecha_str,
        "bloques": bloques,
        "fecha_valida": fecha_valida,
        "fecha_minima": fecha_minima,
    })


@user_passes_test(es_solicitante, login_url="login_solicitante")
def solicitar_area(request):
    """Paso previo de selección de área académica para usuarios con múltiples áreas activas."""
    areas = request.user.areas.filter(activa=True)
    if not areas.exists():
        return render(request, "solicitudes/sin_area.html")

    if areas.count() == 1:
        area_unica = areas.first()
        wizard = SolicitudWizard(request.session)
        wizard.guardar_area(area_unica.id, area_unica.nombre)
        return redirect(reverse("solicitar"))

    wizard = SolicitudWizard(request.session)
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
            initial["area"] = wizard.datos.get("area_id")
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
    areas = request.user.areas.filter(activa=True)
    if not areas.exists():
        return render(request, "solicitudes/sin_area.html")

    wizard = SolicitudWizard(request.session)
    tiene_multiples_areas = areas.count() > 1

    # Si solicita cambiar área explícitamente y tiene múltiples áreas:
    if request.GET.get("cambiar_area") or request.GET.get("cambiar"):
        if tiene_multiples_areas:
            wizard.limpiar_horario()
            return redirect(f"{reverse('solicitar_area')}?cambiar=1")

    # Evaluación de área previa:
    if not wizard.tiene_area:
        if not tiene_multiples_areas:
            area_unica = areas.first()
            wizard.guardar_area(area_unica.id, area_unica.nombre)
        else:
            return redirect(reverse("solicitar_area"))
    else:
        area_sesion_id = wizard.datos.get("area_id")
        if not areas.filter(id=area_sesion_id).exists():
            if not tiene_multiples_areas:
                area_unica = areas.first()
                wizard.guardar_area(area_unica.id, area_unica.nombre, reset_horario=True)
            else:
                return redirect(f"{reverse('solicitar_area')}?cambiar=1")

    paso_param = request.POST.get("paso", request.GET.get("paso"))
    if not paso_param:
        paso_solicitado = PasoSolicitud.HORARIO
    else:
        paso_solicitado = PasoSolicitud.resolver(paso_param)

    paso_actual = paso_solicitado.validar_acceso(wizard.datos)
    if paso_actual != paso_solicitado and request.method == "GET":
        return redirect(f"{reverse('solicitar')}?paso={paso_actual.value}")

    if paso_actual == PasoSolicitud.HORARIO:
        return _manejar_paso_horario(request, wizard, puede_cambiar_area=tiene_multiples_areas)
    elif paso_actual == PasoSolicitud.DATOS:
        return _manejar_paso_datos(request, wizard, puede_cambiar_area=tiene_multiples_areas)
    elif paso_actual == PasoSolicitud.CONFIRMACION:
        return _manejar_paso_confirmacion(request, wizard, puede_cambiar_area=tiene_multiples_areas)

    return _manejar_paso_horario(request, wizard, puede_cambiar_area=tiene_multiples_areas)


def _manejar_paso_horario(request, wizard: SolicitudWizard, puede_cambiar_area: bool = False):
    error_bloques = None
    fecha_minima, fecha_maxima = obtener_limites_reserva()

    if request.method == "POST":
        fecha_str = request.POST.get("fecha")
        raw_bloques = request.POST.getlist("bloques")
        bloques_ids = [int(b) for b in raw_bloques if b.isdigit()]

        fecha_obj = None
        if fecha_str:
            try:
                fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                fecha_str = None

        if not fecha_str or not fecha_obj:
            error_bloques = "Por favor, selecciona un día disponible en el calendario."
        elif fecha_obj < fecha_minima or fecha_obj > fecha_maxima:
            error_bloques = "La fecha seleccionada no está dentro del período permitido."
        elif not bloques_ids:
            error_bloques = "Por favor, selecciona al menos un bloque de horario para continuar."
        else:
            bloques_disponibles = [
                b for b in obtener_bloques_dia_para_usuario(fecha=fecha_obj, usuario=request.user)
                if b.id in bloques_ids and b.disponible
            ]
            if len(bloques_disponibles) != len(bloques_ids):
                error_bloques = "Uno o más de los bloques seleccionados ya no están disponibles. Por favor, selecciona otros."
            else:
                horas_texto = ", ".join(b.texto for b in bloques_disponibles)
                wizard.guardar_horario(fecha_str, bloques_ids, horas_texto)
                return redirect(f"{reverse('solicitar')}?paso={PasoSolicitud.DATOS.value}")

    datos_sesion = wizard.datos
    fecha_seleccionada_str = datos_sesion.get("fecha")
    bloques_seleccionados_ids = datos_sesion.get("bloques_ids", [])

    contexto = construir_calendario_contexto(
        request,
        fecha_str=fecha_seleccionada_str,
        bloques_seleccionados_ids=bloques_seleccionados_ids,
        paso=PasoSolicitud.HORARIO.value,
    )
    contexto.update({
        "paso": PasoSolicitud.HORARIO.value,
        "error_paso": error_bloques,
        "error_bloques": error_bloques,
        "reserva": wizard.obtener_resumen(),
        "puede_cambiar_area": puede_cambiar_area,
    })
    return render(request, "solicitudes/solicitar.html", contexto)


def _manejar_paso_datos(request, wizard: SolicitudWizard, puede_cambiar_area: bool = False):
    datos_sesion = wizard.datos
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
            "motivo": datos_sesion.get("motivo", ""),
            "observaciones": datos_sesion.get("observaciones", ""),
            "personas": datos_sesion.get("personas", 1),
        }
        form = SolicitudForm(initial=initial_form, usuario=request.user, exigir_terminos=False)

        initial_formset = datos_sesion.get("acompanantes", [])
        formset = AcompananteFormSet(initial=initial_formset)

    personas_inicial = datos_sesion.get("personas", 1)
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
                wizard.limpiar()
                return render(request, "solicitudes/enviada.html", {
                    "solicitud": solicitud_obj,
                    "reserva": resumen,
                    "acompanantes": resumen["acompanantes"],
                })
            except ValidationError as e:
                error_terminos = "; ".join(e.messages) if hasattr(e, "messages") else str(e)

    contexto = {
        "paso": PasoSolicitud.CONFIRMACION.value,
        "reserva": resumen,
        "error_terminos": error_terminos,
        "terminos": terminos_texto,
        "puede_cambiar_area": puede_cambiar_area,
    }
    return render(request, "solicitudes/solicitar.html", contexto)
