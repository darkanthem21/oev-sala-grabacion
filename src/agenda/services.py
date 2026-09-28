from datetime import date
from .models import Bloque


def obtener_bloques_mes(year: int, month: int, disponible: bool = True):
    """
    Proveedor de datos: Retorna los bloques correspondientes a un año y mes específicos.
    Si disponible es True o False, filtra por dicho estado; si es None, retorna todos.
    """
    qs = Bloque.objects.filter(fecha__year=year, fecha__month=month)
    if disponible is not None:
        qs = qs.filter(disponible=disponible)
    return qs


def obtener_bloques_dia(fecha: date, solo_disponibles: bool = False, ordenado: bool = True):
    """
    Proveedor de datos: Retorna los bloques para una fecha específica.
    """
    qs = Bloque.objects.filter(fecha=fecha)
    if solo_disponibles:
        qs = qs.filter(disponible=True)
    if ordenado:
        qs = qs.order_by("hora_inicio")
    return qs


def obtener_dias_con_bloques_disponibles(year: int, month: int):
    """
    Proveedor de datos: Retorna un conjunto con los números de día del mes
    que cuentan con al menos un bloque disponible.
    """
    return set(
        Bloque.objects.filter(
            fecha__year=year,
            fecha__month=month,
            disponible=True,
        ).values_list("fecha__day", flat=True)
    )
