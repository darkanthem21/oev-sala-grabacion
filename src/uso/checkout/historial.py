"""Ventana de dos meses, semanas y agrupación diaria del historial administrativo."""

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from itertools import groupby

from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.utils import timezone

from .models import Checkout, RespuestaCheckout


def inicio_historial(hoy):
    anio, mes = divmod(hoy.year * 12 + hoy.month - 1 - 2, 12)
    mes += 1
    return date(anio, mes, min(hoy.day, monthrange(anio, mes)[1]))


def registros_recientes(ahora=None):
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    desde = timezone.make_aware(datetime.combine(inicio_historial(hoy), time.min))
    casos = RespuestaCheckout.objects.faltas_integridad().filter(checkout_id=OuterRef("pk"))
    return Checkout.objects.filter(registrado_en__gte=desde, registrado_en__lte=ahora).select_related(
        "ticket__bloque", "ticket__solicitud__solicitante", "ticket__solicitud__area", "registrado_por", "editado_por",
    ).annotate(tiene_reporte=Exists(casos)).order_by("-registrado_en", "-pk")


def historial_semanal(semana=None, pagina=None, ahora=None):
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    desde = inicio_historial(hoy)
    lunes = hoy - timedelta(days=hoy.weekday())
    semanas = []
    while lunes + timedelta(days=6) >= desde:
        semanas.append({"lunes": lunes, "desde": max(lunes, desde), "hasta": min(lunes + timedelta(days=6), hoy)})
        lunes -= timedelta(days=7)
    try:
        elegida = date.fromisoformat(semana or "")
    except ValueError:
        elegida = semanas[0]["lunes"]
    seleccionada = next((s for s in semanas if s["lunes"] == elegida), semanas[0])
    for item in semanas:
        item["activa"] = item is seleccionada
    inicio = timezone.make_aware(datetime.combine(seleccionada["desde"], time.min))
    fin = timezone.make_aware(datetime.combine(seleccionada["hasta"] + timedelta(days=1), time.min))
    registros = registros_recientes(ahora).filter(registrado_en__gte=inicio, registrado_en__lt=fin)
    resultados = Paginator(registros, 30).get_page(pagina)
    dias = [{"fecha": fecha, "registros": list(filas)} for fecha, filas in groupby(
        resultados.object_list, key=lambda r: timezone.localdate(r.registrado_en),
    )]
    return {"desde": desde, "hasta": hoy, "semanas": semanas, "semana": seleccionada, "pagina": resultados, "dias": dias}
