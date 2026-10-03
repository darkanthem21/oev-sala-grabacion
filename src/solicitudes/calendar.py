import calendar
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set

from .services import obtener_bloques_dia_para_usuario, obtener_dias_con_disponibilidad
from .wizard import obtener_limites_reserva


class AgendaCalendar(calendar.HTMLCalendar):
    """Generador HTML para la grilla de disponibilidad del calendario."""

    DIAS_SEMANA = ["LUN", "MAR", "MIE", "JUE", "VIE", "SÁB", "DOM"]

    def __init__(
        self,
        dias_disponibles: Set[int],
        year: int,
        month: int,
        fecha_seleccionada: Optional[date] = None,
        fecha_minima: Optional[date] = None,
        fecha_maxima: Optional[date] = None,
    ):
        super().__init__()
        self.dias_disponibles = dias_disponibles
        self.year = year
        self.month = month
        self.fecha_seleccionada = fecha_seleccionada
        self.fecha_minima = fecha_minima
        self.fecha_maxima = fecha_maxima

    def formatweekday(self, day):
        return f'<th class="{self.cssclasses_weekday_head[day]}">{self.DIAS_SEMANA[day]}</th>'

    def formatday(self, day, weekday):
        if day == 0:
            return '<td class="noday">&nbsp;</td>'

        css_class = self.cssclasses[weekday]
        date_str = f"{self.year}-{self.month:02d}-{day:02d}"
        dia_fecha = date(self.year, self.month, day)

        es_valido = True
        if self.fecha_minima and dia_fecha < self.fecha_minima:
            es_valido = False
            css_class += " bloqueado-anticipacion"
        if self.fecha_maxima and dia_fecha > self.fecha_maxima:
            es_valido = False

        if day in self.dias_disponibles and es_valido:
            css_class += " available dia-seleccionable"
            if self.fecha_seleccionada and self.fecha_seleccionada == dia_fecha:
                css_class += " selected"
            return (
                f'<td class="{css_class}" data-date="{date_str}">'
                f'<a href="?year={self.year}&month={self.month}&fecha={date_str}" '
                f'class="dia-enlace" '
                f'hx-get="/solicitar/bloques/?fecha={date_str}" '
                f'hx-target="#panel-bloques" '
                f'hx-swap="innerHTML" '
                f'hx-push-url="false" '
                f'onclick="document.querySelectorAll(\'.calendario td.selected\').forEach(function(el){{el.classList.remove(\'selected\');}}); this.closest(\'td\').classList.add(\'selected\'); document.querySelectorAll(\'input[name=fecha]\').forEach(function(el){{el.value=\'{date_str}\';}});">'
                f"{day}</a></td>"
            )

        return f'<td class="{css_class}" data-date="{date_str}">{day}</td>'


def construir_calendario_contexto(
    request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    fecha_str: Optional[str] = None,
    bloques_seleccionados_ids: Optional[List[int]] = None,
    paso: Optional[int] = None,
) -> Dict[str, Any]:
    """Construye el calendario mensual y su contexto de navegación."""
    fecha_minima, fecha_maxima = obtener_limites_reserva()

    if year is None or month is None:
        try:
            year = int(request.GET.get("year", fecha_minima.year))
            month = int(request.GET.get("month", fecha_minima.month))
        except (ValueError, TypeError):
            year = fecha_minima.year
            month = fecha_minima.month

    # Validar límites de mes permitidos
    _, ultimo_dia_mes = calendar.monthrange(year, month)
    if date(year, month, ultimo_dia_mes) < fecha_minima:
        year, month = fecha_minima.year, fecha_minima.month
    elif date(year, month, 1) > date(fecha_maxima.year, fecha_maxima.month, 1):
        year, month = fecha_maxima.year, fecha_maxima.month

    if fecha_str is None:
        fecha_str = request.POST.get("fecha") if request.method == "POST" else request.GET.get("fecha")

    fecha_seleccionada = None
    bloques_seleccionados = []
    if fecha_str:
        try:
            fecha_seleccionada = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            if fecha_seleccionada < fecha_minima or fecha_seleccionada > fecha_maxima:
                fecha_seleccionada = None
                fecha_str = None
            else:
                bloques_seleccionados = obtener_bloques_dia_para_usuario(
                    fecha=fecha_seleccionada,
                    usuario=getattr(request, "user", None),
                )
        except ValueError:
            fecha_str = None

    dias_disponibles = obtener_dias_con_disponibilidad(year=year, month=month)
    cal = AgendaCalendar(
        dias_disponibles,
        year,
        month,
        fecha_seleccionada=fecha_seleccionada,
        fecha_minima=fecha_minima,
        fecha_maxima=fecha_maxima,
    )
    html_cal = cal.formatmonth(year, month)

    mes_anterior = month - 1 if month > 1 else 12
    anio_anterior = year if month > 1 else year - 1
    mes_siguiente = month + 1 if month < 12 else 1
    anio_siguiente = year if month < 12 else year + 1

    _, ultimo_dia_anterior = calendar.monthrange(anio_anterior, mes_anterior)
    mostrar_anterior = date(anio_anterior, mes_anterior, ultimo_dia_anterior) >= fecha_minima
    mostrar_siguiente = date(anio_siguiente, mes_siguiente, 1) <= date(fecha_maxima.year, fecha_maxima.month, 1)

    meses_espanol = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre")
    ]
    nombre_mes_actual = dict(meses_espanol)[month]
    meses_contexto = [
        (
            m_num,
            m_nombre,
            date(year, m_num, calendar.monthrange(year, m_num)[1]) >= fecha_minima
            and date(year, m_num, 1) <= date(fecha_maxima.year, fecha_maxima.month, 1),
        )
        for m_num, m_nombre in meses_espanol
    ]

    reserva = {}
    if hasattr(request, "session"):
        reserva = request.session.get("solicitud_reserva", {})

    return {
        "calendario": html_cal,
        "year": year,
        "month": month,
        "nombre_mes_actual": nombre_mes_actual,
        "prev_year": anio_anterior,
        "prev_month": mes_anterior,
        "next_year": anio_siguiente,
        "next_month": mes_siguiente,
        "mostrar_anterior": mostrar_anterior,
        "mostrar_siguiente": mostrar_siguiente,
        "meses": meses_contexto,
        "anios_permitidos": range(fecha_minima.year, fecha_maxima.year + 1),
        "fecha_seleccionada": fecha_seleccionada,
        "fecha_str": fecha_str,
        "bloques_seleccionados": bloques_seleccionados,
        "bloques_seleccionados_ids": bloques_seleccionados_ids or [],
        "paso": paso,
        "fecha_minima": fecha_minima,
        "reserva": reserva,
    }
