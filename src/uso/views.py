"""Panel diario de bloques del personal de apoyo."""

from datetime import date, timedelta

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.utils import timezone

from agenda.models import bloqueos_por_fecha
from . import services
from .checkout.permissions import es_apoyo


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
