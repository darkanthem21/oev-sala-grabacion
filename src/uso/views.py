from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import user_passes_test
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from agenda.models import bloqueos_por_fecha
from personas.models import Rol

from . import services

# ponytail: el check-out simulado vive en la sesión, así que solo lo ve quien lo
# envió y se pierde al cerrarla. Pasa a la base cuando US-15 tenga su modelo.
SESION = "checkouts_simulados"


def es_apoyo(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.APOYO)


def _enviados(request):
    return request.session.get(SESION, {})


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
        "bloques": services.bloques_del_dia(fecha, _enviados(request)),
        # US-17 AC2: también cuando ese día no hay nada reservado.
        "bloqueos": bloqueos_por_fecha(fecha, fecha).get(fecha, []),
    })


@user_passes_test(es_apoyo, login_url="login_apoyo")
def checkout(request, codigo):
    """La entrada al check-out de un bloque. El formulario es US-15.

    Solo se llega con el bloque terminado: antes no hay sala que revisar, y uno
    cancelado no se usó. Uno ya completado se muestra pero no se vuelve a enviar
    (US-15 AC4).
    """
    enviados = _enviados(request)
    bloque = services.buscar(codigo, enviados)
    if bloque is None or bloque["checkout"] is None:
        raise Http404
    volver = f"{reverse('panel_apoyo')}?fecha={bloque['fecha']:%Y-%m-%d}"

    if request.method == "POST" and bloque["checkout"] == "pendiente":
        enviados[codigo] = {"por": request.user.email, "en": timezone.now().isoformat()}
        request.session[SESION] = enviados
        return redirect(volver)

    registro = enviados.get(codigo)
    if registro:
        registro = {**registro, "en": timezone.localtime(datetime.fromisoformat(registro["en"]))}
    return render(request, "uso/checkout.html", {
        "bloque": bloque,
        "registro": registro,
        "volver": volver,
    })
