"""Panel diario de bloques del personal de apoyo (US-14) y pestaña Sanciones
del administrador (US-12)."""

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_http_methods

from agenda.models import bloqueos_por_fecha
from configuracion.models import Parametros
from personas.services import aplicar, levantar, termino_por_defecto
from personas.forms import AplicarSancionForm, LevantarSancionForm
from personas.models import Sancion, Usuario
from personas.permisos import solo_administradores
from . import services
from .checkout.permissions import es_apoyo
from .forms import FiltroSancionesForm

PERSONAS_POR_PAGINA = 25


@user_passes_test(es_apoyo, login_url="login_apoyo")
def bloques(request):
    """US-14: los bloques de un día, hoy si no se pide otro (AC3)."""
    hoy = timezone.localdate()
    try:
        fecha = date.fromisoformat(request.GET.get("fecha", ""))
    except ValueError:
        fecha = hoy
    return render(request, "uso/bloques.html", {
        "fecha": fecha,
        "hoy": hoy,
        "anterior": fecha - timedelta(days=1),
        "siguiente": fecha + timedelta(days=1),
        "bloques": services.bloques_del_dia(fecha),
        # US-17 AC2: también cuando ese día no hay nada reservado.
        "bloqueos": bloqueos_por_fecha(fecha, fecha).get(fecha, []),
    })


def _nombre(usuario):
    return usuario.get_full_name() or usuario.email


def _con_filtros(url, consulta):
    """La dirección con los filtros del listado que trajo el formulario,
    normalizados: vuelven a la misma página que se estaba viendo."""
    consulta = QueryDict(consulta).urlencode()
    return f"{url}?{consulta}" if consulta else url


def _levantar(request):
    """US-10 y US-12 T7: levanta la sanción del POST y deja el aviso. Si la
    persona tiene otra vigente, el aviso lo dice en vez de prometer que ya puede
    pedir la sala."""
    sancion = get_object_or_404(Sancion.objects.select_related("usuario"), pk=request.POST.get("sancion"))
    formulario = LevantarSancionForm(request.POST)
    if not formulario.is_valid():
        messages.error(request, " ".join(formulario.errors["motivo"]))
        return sancion.usuario
    try:
        levantar(sancion, request.user, formulario.cleaned_data["motivo"])
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return sancion.usuario
    persona = sancion.usuario
    otra = persona.sancion_vigente
    if otra:
        messages.warning(request, f"Levantaste la sanción de {_nombre(persona)}, pero tiene otra vigente: "
                                  f"sigue sin poder solicitar la sala hasta el {otra.hasta}.")
    else:
        messages.success(request, f"Levantaste la sanción de {_nombre(persona)}. Ya puede solicitar la sala.")
    return persona


@solo_administradores
@require_http_methods(["GET", "HEAD", "POST"])
def sanciones(request):
    """US-12 T4: las personas con sus incidentes, inasistencias y sanción, con
    filtros por GET y de PERSONAS_POR_PAGINA por página.

    Vive en `uso` y no en `personas` porque cuenta check-outs, y personas no
    puede depender de uso. Conserva la dirección y el nombre de US-10. El POST es
    el Levantar de cada fila, como en US-10, y vuelve con una redirección a la
    misma página y filtros.
    """
    if request.method == "POST":
        _levantar(request)
        return redirect(_con_filtros(reverse("panel_sanciones"), request.POST.get("volver", "")))

    filtros = FiltroSancionesForm(request.GET)
    personas = services.filtrar_personas(services.historial_personas(), **filtros.datos())
    consulta = request.GET.copy()
    consulta.pop("pagina", None)
    consulta["pagina"] = ""
    contexto = {
        "pestana": "sanciones",
        "filtros": filtros,
        "filtrado": any(v for k, v in consulta.items() if k != "pagina"),
        "url_pagina": f"{reverse('panel_sanciones')}?{consulta.urlencode()}",
        "consulta_completa": request.GET.urlencode(),
        "pagina": Paginator(personas, PERSONAS_POR_PAGINA).get_page(request.GET.get("pagina")),
        "umbral": Parametros.cargar().inasistencias_para_sancion,
    }
    for persona in contexto["pagina"]:
        persona.estado_texto = services.ESTADOS_SANCION[persona.estado_sancion]
    # Como el historial de US-11: htmx pide solo la tabla, salvo al restaurar
    # el historial del navegador.
    if request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request"):
        respuesta = render(request, "uso/sanciones/_tabla.html", contexto)
    else:
        respuesta = render(request, "uso/sanciones/listado.html", contexto)
    patch_vary_headers(respuesta, ["HX-Request"])
    return respuesta


@solo_administradores
@require_http_methods(["GET", "HEAD", "POST"])
def sanciones_de(request, usuario_id):
    """US-12 T5 a T7: el historial de una persona, y desde ahí aplicar o
    levantar. Los POST vuelven con una redirección, para que recargar no
    sancione dos veces."""
    persona = get_object_or_404(Usuario, pk=usuario_id)
    hoy = timezone.localdate()
    aqui = reverse("sanciones_de", args=[persona.pk])
    formulario = None
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "levantar":
            _levantar(request)
            return redirect(_con_filtros(aqui, request.POST.get("volver", "")))
        if accion != "aplicar":
            return HttpResponseBadRequest()
        formulario = AplicarSancionForm(request.POST)
        if formulario.is_valid():
            try:
                sancion = aplicar(persona, quien=request.user, **formulario.cleaned_data)
            except ValidationError as error:
                # Lo de un campo va bajo el campo; el cruce, arriba del formulario.
                for campo, errores in error.message_dict.items():
                    formulario.add_error(campo if campo in formulario.fields else None, errores)
            else:
                messages.success(request, f"Sancionaste a {_nombre(persona)} {sancion.periodo}. Puede volver a "
                                          f"solicitar desde el {sancion.rehabilita}; se le avisó por correo.")
                return redirect(_con_filtros(aqui, request.POST.get("volver", "")))
    parametros = Parametros.cargar()
    if formulario is None:
        formulario = AplicarSancionForm(initial={
            "inicio": hoy, "termino": termino_por_defecto(hoy, parametros.dias_sancion),
        })
    eventos = services.detalle_de(persona, hoy)
    return render(request, "uso/sanciones/detalle.html", {
        "pestana": "sanciones",
        "persona": persona,
        "eventos": eventos,
        "vigentes": [e["sancion"] for e in eventos if e["tipo"] == "sancion" and e["estado"] == "vigente"],
        "incidentes": sum(e["tipo"] == "incidente" for e in eventos),
        "inasistencias": sum(e["tipo"] == "inasistencia" for e in eventos),
        "aplicar": formulario,
        "parametros": parametros,
        # Los filtros del listado del que se llegó, para volver a la misma página.
        "volver": request.POST.get("volver", "") if request.method == "POST" else request.GET.urlencode(),
    })
