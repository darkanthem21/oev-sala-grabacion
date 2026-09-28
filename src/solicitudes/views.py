import calendar
from datetime import date, datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from agenda.services import obtener_bloques_dia, obtener_bloques_mes
from .forms import MAXIMO_ACOMPANANTES, MAXIMO_PERSONAS, AcompananteFormSet, SolicitudForm


class AgendaCalendar(calendar.HTMLCalendar):
    DIAS_SEMANA = ["LUN", "MAR", "MIE", "JUE", "VIE", "SÁB", "DOM"]

    def __init__(self, bloques, year, month, fecha_seleccionada=None):
        super().__init__()
        self.bloques = {b.fecha.day for b in bloques}
        self.year = year
        self.month = month
        self.fecha_seleccionada = fecha_seleccionada

    def formatweekday(self, day):
        return f'<th class="{self.cssclasses_weekday_head[day]}">{self.DIAS_SEMANA[day]}</th>'

    def formatday(self, day, weekday):
        if day == 0:
            return '<td class="noday">&nbsp;</td>'
        
        css_class = self.cssclasses[weekday]
        date_str = f"{self.year}-{self.month:02d}-{day:02d}"
        
        if day in self.bloques:
            css_class += ' available dia-seleccionable'
            if self.fecha_seleccionada and self.fecha_seleccionada == date(self.year, self.month, day):
                css_class += ' selected'
            return f'<td class="{css_class}" data-date="{date_str}"><a href="?year={self.year}&month={self.month}&fecha={date_str}" class="dia-enlace">{day}</a></td>'
        
        return f'<td class="{css_class}" data-date="{date_str}">{day}</td>'


def calendario(request):
    """
    Vista del frontend para la interacción del usuario con el calendario de disponibilidad.
    Consume la información provista por la aplicación agenda.
    """
    FECHA_MINIMA = date(2023, 1, 1)
    FECHA_MAXIMA = date(2028, 12, 31)

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

    # Bloques del día seleccionado (si se pasó en el query param o POST fecha)
    fecha_str = request.POST.get('fecha') if request.method == 'POST' else request.GET.get('fecha')
    if not fecha_str and request.method == 'POST':
        fecha_str = request.GET.get('fecha')

    fecha_seleccionada = None
    bloques_seleccionados = []
    if fecha_str:
        try:
            fecha_seleccionada = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            bloques_seleccionados = obtener_bloques_dia(fecha_seleccionada)
        except ValueError:
            fecha_str = None

    mensaje_confirmacion = None
    error_confirmacion = None
    bloques_seleccionados_ids = []

    if request.method == "POST":
        bloques_ids = request.POST.getlist("bloques")
        bloques_seleccionados_ids = [int(b) for b in bloques_ids if b.isdigit()]

        if not fecha_str or not fecha_seleccionada:
            error_confirmacion = "Por favor, selecciona un día del calendario."
        elif not bloques_seleccionados_ids:
            error_confirmacion = f"Día seleccionado: {fecha_seleccionada.strftime('%d/%m/%Y')}. Por favor, selecciona al menos un bloque disponible."
        else:
            bloques_disponibles = [
                b for b in bloques_seleccionados
                if b.id in bloques_seleccionados_ids and b.disponible
            ]
            if not bloques_disponibles:
                error_confirmacion = "Ninguno de los bloques seleccionados está disponible."
            else:
                horas_texto = ", ".join(
                    f"{b.hora_inicio.strftime('%H:%M')} - {b.hora_final.strftime('%H:%M')}"
                    for b in bloques_disponibles
                )
                mensaje_confirmacion = (
                    f"Día seleccionado: {fecha_seleccionada.strftime('%d/%m/%Y')}. "
                    f"Bloque(s) seleccionado(s): {horas_texto}."
                )

    # Consumir bloques disponibles para el mes y año desde el proveedor agenda
    bloques = obtener_bloques_mes(year, month, disponible=True)
    
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

    return render(request, "solicitudes/calendario.html", {
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
        "bloques_seleccionados_ids": bloques_seleccionados_ids,
        "mensaje_confirmacion": mensaje_confirmacion,
        "error_confirmacion": error_confirmacion,
    })


def bloques_dia(request):
    """
    Vista del frontend para consultar y desplegar los bloques de una fecha.
    Consume los datos de la aplicación agenda y renderiza el fragmento HTML correspondiente.
    """
    fecha_str = request.GET.get('fecha')
    fecha = None
    bloques = []
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            bloques = obtener_bloques_dia(fecha)
        except ValueError:
            pass

    return render(request, "solicitudes/bloques_dia.html", {
        "bloques": bloques,
        "fecha": fecha,
        "fecha_str": fecha_str,
    })


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
        # US-04 AC5 pide que el cliente edite este texto sin recompilar. Hasta
        # que exista el modulo `configuracion` viaja por entorno, igual que los
        # umbrales de bloqueo de US-01.
        "terminos": settings.TERMINOS_Y_CONDICIONES,
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
