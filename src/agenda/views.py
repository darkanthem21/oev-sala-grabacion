import calendar
from django.shortcuts import render
from datetime import datetime, date
from .models import Bloque

class AgendaCalendar(calendar.HTMLCalendar):
    def __init__(self, bloques, year, month, fecha_seleccionada=None):
        super().__init__()
        self.bloques = {b.fecha.day for b in bloques}
        self.year = year
        self.month = month
        self.fecha_seleccionada = fecha_seleccionada

    def formatday(self, day, weekday):
        if day == 0:
            return '<td class="noday">&nbsp;</td>'
        
        css_class = self.cssclasses[weekday]
        if day in self.bloques:
            css_class += ' available'
        
        date_str = f"{self.year}-{self.month:02d}-{day:02d}"
        if self.fecha_seleccionada and self.fecha_seleccionada == date(self.year, self.month, day):
            css_class += ' selected'
        
        return f'<td class="{css_class} dia-seleccionable" data-date="{date_str}">{day}</td>'

def calendario(request):
    # --- MÉTODO PLACEHOLDER: LÍMITES DE VISUALIZACIÓN ---
    # Aquí defines la fecha mínima y máxima que el sistema permite visualizar.
    # Puede abarcar los años que desees.
    FECHA_MINIMA = date(2023, 1, 1)
    FECHA_MAXIMA = date(2028, 12, 31)
    # ----------------------------------------------------

    ahora = datetime.now()
    
    # Obtener mes y año desde la URL; si no existen o son inválidos, usar el actual
    try:
        year = int(request.GET.get('year', ahora.year))
        month = int(request.GET.get('month', ahora.month))
    except ValueError:
        year = ahora.year
        month = ahora.month

    # Validar que la fecha solicitada esté dentro de los límites permitidos
    fecha_solicitada = date(year, month, 1)
    if fecha_solicitada < date(FECHA_MINIMA.year, FECHA_MINIMA.month, 1):
        year, month = FECHA_MINIMA.year, FECHA_MINIMA.month
    elif fecha_solicitada > date(FECHA_MAXIMA.year, FECHA_MAXIMA.month, 1):
        year, month = FECHA_MAXIMA.year, FECHA_MAXIMA.month

    # Bloques del día seleccionado (si se pasó en el query param fecha)
    fecha_str = request.GET.get('fecha')
    fecha_seleccionada = None
    bloques_seleccionados = []
    if fecha_str:
        try:
            fecha_seleccionada = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            bloques_seleccionados = Bloque.objects.filter(fecha=fecha_seleccionada).order_by('hora_inicio')
        except ValueError:
            fecha_str = None

    # Filtrar bloques para el mes y año en curso
    bloques = Bloque.objects.filter(fecha__year=year, fecha__month=month, disponible=True)
    
    cal = AgendaCalendar(bloques, year, month, fecha_seleccionada=fecha_seleccionada)
    html_cal = cal.formatmonth(year, month)

    # Lógica de navegación (Cálculo del mes anterior y siguiente)
    mes_anterior = month - 1 if month > 1 else 12
    anio_anterior = year if month > 1 else year - 1
    
    mes_siguiente = month + 1 if month < 12 else 1
    anio_siguiente = year if month < 12 else year + 1

    # Verificar si los botones prev/next se salen de los límites
    mostrar_anterior = date(anio_anterior, mes_anterior, 1) >= date(FECHA_MINIMA.year, FECHA_MINIMA.month, 1)
    mostrar_siguiente = date(anio_siguiente, mes_siguiente, 1) <= date(FECHA_MAXIMA.year, FECHA_MAXIMA.month, 1)

    # Nombres de meses para los selectores y el título
    meses_espanol = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'), 
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'), 
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    nombre_mes_actual = dict(meses_espanol)[month]

    return render(request, "agenda/calendario.html", {
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
        "meses": meses_espanol,
        "anios_permitidos": range(FECHA_MINIMA.year, FECHA_MAXIMA.year + 1),
        "fecha_seleccionada": fecha_seleccionada,
        "fecha_str": fecha_str,
        "bloques_seleccionados": bloques_seleccionados,
    })


def bloques_dia(request):
    fecha_str = request.GET.get('fecha')
    fecha = None
    bloques = []
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            bloques = Bloque.objects.filter(fecha=fecha).order_by('hora_inicio')
        except ValueError:
            pass

    return render(request, "agenda/bloques_dia.html", {
        "bloques": bloques,
        "fecha": fecha,
        "fecha_str": fecha_str,
    })