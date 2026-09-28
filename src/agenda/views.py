from datetime import datetime
from django.http import JsonResponse
from .services import obtener_bloques_dia, obtener_bloques_mes, obtener_dias_con_bloques_disponibles


def bloques_dia(request):
    """
    Proveedor de datos HTTP (API JSON):
    Retorna la lista de bloques correspondientes a una fecha dada.
    """
    fecha_str = request.GET.get("fecha")
    if not fecha_str:
        return JsonResponse({"error": "Parámetro 'fecha' requerido (formato YYYY-MM-DD)"}, status=400)

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, status=400)

    bloques = obtener_bloques_dia(fecha)
    data = [
        {
            "id": b.id,
            "hora_inicio": b.hora_inicio.strftime("%H:%M"),
            "hora_final": b.hora_final.strftime("%H:%M"),
            "disponible": b.disponible,
        }
        for b in bloques
    ]
    return JsonResponse({
        "fecha": fecha_str,
        "total": len(data),
        "bloques": data,
    })


def disponibilidad_mes(request):
    """
    Proveedor de datos HTTP (API JSON):
    Retorna los días con bloques disponibles para un año y mes específicos.
    """
    ahora = datetime.now()
    try:
        year = int(request.GET.get("year", ahora.year))
        month = int(request.GET.get("month", ahora.month))
    except ValueError:
        return JsonResponse({"error": "Parámetros 'year' y 'month' deben ser enteros"}, status=400)

    dias_disponibles = sorted(list(obtener_dias_con_bloques_disponibles(year, month)))
    return JsonResponse({
        "year": year,
        "month": month,
        "dias_disponibles": dias_disponibles,
    })