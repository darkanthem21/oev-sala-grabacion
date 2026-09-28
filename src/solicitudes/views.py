import calendar
from datetime import date, datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from agenda.services import obtener_bloques_dia, obtener_bloques_mes
from .forms import MAXIMO_ACOMPANANTES, MAXIMO_PERSONAS, AcompananteFormSet, SolicitudForm
from .wizard import PasoSolicitud, SolicitudWizard, obtener_limites_reserva


class AgendaCalendar(calendar.HTMLCalendar):
    DIAS_SEMANA = ["LUN", "MAR", "MIE", "JUE", "VIE", "SÁB", "DOM"]

    def __init__(self, bloques, year, month, fecha_seleccionada=None, fecha_minima=None, fecha_maxima=None):
        super().__init__()
        self.bloques = {b.fecha.day for b in bloques}
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
        if self.fecha_maxima and dia_fecha > self.fecha_maxima:
            es_valido = False
        
        if day in self.bloques and es_valido:
            css_class += ' available dia-seleccionable'
            if self.fecha_seleccionada and self.fecha_seleccionada == dia_fecha:
                css_class += ' selected'
            return (
                f'<td class="{css_class}" data-date="{date_str}">'
                f'<a href="?year={self.year}&month={self.month}&fecha={date_str}" '
                f'class="dia-enlace" '
                f'hx-get="/solicitar/bloques/?fecha={date_str}" '
                f'hx-target="#panel-bloques" '
                f'hx-swap="innerHTML" '
                f'hx-push-url="false" '
                f'onclick="document.querySelectorAll(\'.calendario td.selected\').forEach(function(el){{el.classList.remove(\'selected\');}}); this.closest(\'td\').classList.add(\'selected\');">'
                f'{day}</a></td>'
            )
        
        return f'<td class="{css_class}" data-date="{date_str}">{day}</td>'


def _construir_calendario_contexto(request, year=None, month=None, fecha_str=None, bloques_seleccionados_ids=None, paso=None):
    """
    Construye el calendario mensual y su contexto de navegación para ser consumido
    tanto por la vista general de calendario como por el paso 1 del wizard de reserva.
    No permite la navegación ni selección de meses anteriores al mes actual ni posteriores
    al límite de anticipación máxima configurado.
    """
    fecha_minima, fecha_maxima = obtener_limites_reserva()

    if year is None or month is None:
        try:
            year = int(request.GET.get('year', fecha_minima.year))
            month = int(request.GET.get('month', fecha_minima.month))
        except (ValueError, TypeError):
            year = fecha_minima.year
            month = fecha_minima.month

    # Validar que la fecha solicitada esté dentro de los límites permitidos (nunca meses pasados ni fuera de rango)
    fecha_solicitada = date(year, month, 1)
    if fecha_solicitada < fecha_minima:
        year, month = fecha_minima.year, fecha_minima.month
    elif fecha_solicitada > date(fecha_maxima.year, fecha_maxima.month, 1):
        year, month = fecha_maxima.year, fecha_maxima.month

    if fecha_str is None:
        fecha_str = request.POST.get('fecha') if request.method == 'POST' else request.GET.get('fecha')

    fecha_seleccionada = None
    bloques_seleccionados = []
    if fecha_str:
        try:
            fecha_seleccionada = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            if fecha_seleccionada < fecha_minima or fecha_seleccionada > fecha_maxima:
                fecha_seleccionada = None
                fecha_str = None
            else:
                bloques_seleccionados = obtener_bloques_dia(fecha_seleccionada)
        except ValueError:
            fecha_str = None

    bloques = obtener_bloques_mes(year, month, disponible=True)
    cal = AgendaCalendar(
        bloques,
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

    mostrar_anterior = date(anio_anterior, mes_anterior, 1) >= fecha_minima
    mostrar_siguiente = date(anio_siguiente, mes_siguiente, 1) <= date(fecha_maxima.year, fecha_maxima.month, 1)

    meses_espanol = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    nombre_mes_actual = dict(meses_espanol)[month]
    meses_contexto = [
        (
            m_num,
            m_nombre,
            fecha_minima <= date(year, m_num, 1) <= date(fecha_maxima.year, fecha_maxima.month, 1)
        )
        for m_num, m_nombre in meses_espanol
    ]

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
    }


def calendario(request):
    """
    Vista del frontend para la interacción del usuario con el calendario de disponibilidad.
    Consume la información provista por la aplicación agenda.
    """
    fecha_str = request.POST.get('fecha') if request.method == 'POST' else request.GET.get('fecha')
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
            bloques_dia_disp = obtener_bloques_dia(fecha_obj)
            bloques_disponibles = [
                b for b in bloques_dia_disp
                if b.id in bloques_ids and b.disponible
            ]
            if not bloques_disponibles:
                error_confirmacion = "Ninguno de los bloques seleccionados está disponible."
            else:
                horas_texto = ", ".join(
                    f"{b.hora_inicio.strftime('%H:%M')} - {b.hora_final.strftime('%H:%M')}"
                    for b in bloques_disponibles
                )
                mensaje_confirmacion = (
                    f"Día seleccionado: {fecha_obj.strftime('%d/%m/%Y')}. "
                    f"Bloque(s) seleccionado(s): {horas_texto}."
                )

    ctx = _construir_calendario_contexto(request, fecha_str=fecha_str, bloques_seleccionados_ids=bloques_ids)
    ctx.update({
        "mensaje_confirmacion": mensaje_confirmacion,
        "error_confirmacion": error_confirmacion,
    })
    return render(request, "solicitudes/calendario.html", ctx)


def bloques_dia(request):
    """
    Vista del frontend para consultar y desplegar los bloques de una fecha.
    Consume los datos de la aplicación agenda y renderiza el fragmento HTML correspondiente.
    """
    fecha_str = request.GET.get('fecha')
    fecha = None
    bloques = []
    bloques_seleccionados_ids = []
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            fecha_minima, fecha_maxima = obtener_limites_reserva()
            if fecha < fecha_minima or fecha > fecha_maxima:
                fecha = None
            else:
                bloques = obtener_bloques_dia(fecha)
                # Sincronizar selección previa si existe en la sesión
                solicitud_sesion = request.session.get("solicitud_reserva", {})
                if solicitud_sesion.get("fecha") == fecha_str:
                    bloques_seleccionados_ids = solicitud_sesion.get("bloques_ids", [])
        except ValueError:
            pass

    return render(request, "solicitudes/bloques_dia.html", {
        "bloques": bloques,
        "fecha": fecha,
        "fecha_str": fecha_str,
        "bloques_seleccionados_ids": bloques_seleccionados_ids,
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


def _manejar_paso_horario(request, wizard: SolicitudWizard):
    """Paso 1: Selección de fecha en el calendario y bloques disponibles."""
    error_paso = None
    sesion_reserva = wizard.datos
    fecha_str = request.POST.get("fecha") if request.method == "POST" else sesion_reserva.get("fecha")
    bloques_ids = []

    if request.method == "POST":
        raw_bloques = request.POST.getlist("bloques")
        bloques_ids = [int(b) for b in raw_bloques if b.isdigit()]

        if not fecha_str:
            error_paso = "Por favor, selecciona un día del calendario."
        elif not bloques_ids:
            try:
                f_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                error_paso = f"Día seleccionado: {f_obj.strftime('%d/%m/%Y')}. Por favor, selecciona al menos un bloque disponible."
            except (ValueError, TypeError):
                error_paso = "Por favor, selecciona al menos un bloque disponible."
        else:
            try:
                fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                fecha_minima, fecha_maxima = obtener_limites_reserva()
                if fecha_obj < fecha_minima or fecha_obj > fecha_maxima:
                    error_paso = "La fecha seleccionada no está dentro del período permitido para reservas."
                else:
                    bloques_dia_disp = obtener_bloques_dia(fecha_obj)
                    bloques_validos = [b for b in bloques_dia_disp if b.id in bloques_ids and b.disponible]
                    if not bloques_validos:
                        error_paso = "Ninguno de los bloques seleccionados está disponible."
                    else:
                        horas_texto = ", ".join(
                            f"{b.hora_inicio.strftime('%H:%M')} - {b.hora_final.strftime('%H:%M')}"
                            for b in bloques_validos
                        )
                        wizard.guardar_horario(
                            fecha_str=fecha_str,
                            bloques_ids=[b.id for b in bloques_validos],
                            bloques_texto=horas_texto,
                        )
                        return redirect(f"{reverse('solicitar')}?paso={PasoSolicitud.DATOS.value}")
            except ValueError:
                error_paso = "La fecha seleccionada no es válida."
    else:
        bloques_ids = sesion_reserva.get("bloques_ids", [])

    ctx_cal = _construir_calendario_contexto(
        request,
        fecha_str=fecha_str,
        bloques_seleccionados_ids=bloques_ids,
        paso=PasoSolicitud.HORARIO.value,
    )
    ctx = {
        **ctx_cal,
        "paso": PasoSolicitud.HORARIO.value,
        "error_paso": error_paso,
    }
    return render(request, "solicitudes/solicitar.html", ctx)


def _manejar_paso_datos(request, wizard: SolicitudWizard):
    """Paso 2: Datos de la actividad (área, motivo, observaciones) y acompañantes."""
    errores_paso2 = []
    reserva_info = wizard.obtener_resumen()

    if request.method == "POST":
        form = SolicitudForm(request.POST, usuario=request.user, exigir_terminos=False)
        formset = AcompananteFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            llenos, errs = _revisar_acompanantes(
                formset, form.cleaned_data["personas"] - 1, request.user.email
            )
            if errs:
                errores_paso2 = errs
            else:
                wizard.guardar_datos_actividad(
                    area_id=form.cleaned_data["area"].id,
                    area_nombre=form.cleaned_data["area"].nombre,
                    motivo=form.cleaned_data["motivo"],
                    observaciones=form.cleaned_data.get("observaciones", ""),
                    personas=form.cleaned_data["personas"],
                    acompanantes=[
                        {"nombre": f.cleaned_data["nombre"], "correo": f.cleaned_data["correo"]}
                        for f in llenos
                    ],
                )
                return redirect(f"{reverse('solicitar')}?paso={PasoSolicitud.CONFIRMACION.value}")
    else:
        sesion_reserva = wizard.datos
        initial_data = {}
        if "area_id" in sesion_reserva:
            initial_data["area"] = sesion_reserva["area_id"]
        if "motivo" in sesion_reserva:
            initial_data["motivo"] = sesion_reserva["motivo"]
        if "observaciones" in sesion_reserva:
            initial_data["observaciones"] = sesion_reserva["observaciones"]
        if "personas" in sesion_reserva:
            initial_data["personas"] = sesion_reserva["personas"]

        form = SolicitudForm(initial=initial_data, usuario=request.user, exigir_terminos=False)
        formset_initial = sesion_reserva.get("acompanantes", [])
        formset = AcompananteFormSet(initial=formset_initial)

    personas_inicial, _ = _estado_inicial(form)
    if "personas" in wizard.datos and not form.is_bound:
        personas_inicial = wizard.datos["personas"]

    ctx = {
        "paso": PasoSolicitud.DATOS.value,
        "reserva": reserva_info,
        "form": form,
        "formset": formset,
        "personas_inicial": personas_inicial,
        "maximo_personas": MAXIMO_PERSONAS,
        "maximo_acompanantes": MAXIMO_ACOMPANANTES,
        "errores": errores_paso2,
    }
    return render(request, "solicitudes/solicitar.html", ctx)


def _manejar_paso_confirmacion(request, wizard: SolicitudWizard):
    """Paso 3: Revisión de la reserva, aceptación de términos y confirmación."""
    error_terminos = None
    reserva_info = wizard.obtener_resumen()

    if request.method == "POST":
        acepta = request.POST.get("acepta_terminos")
        if not acepta:
            error_terminos = "Tienes que aceptar los términos y condiciones para enviar la solicitud."
        else:
            solicitud_datos = {
                "fecha": reserva_info["fecha"],
                "bloques_texto": reserva_info["bloques_texto"],
                "area": reserva_info["area_nombre"],
                "motivo": reserva_info["motivo"],
                "observaciones": reserva_info["observaciones"],
                "personas": reserva_info["personas"],
            }
            acompanantes_datos = reserva_info["acompanantes"]

            wizard.limpiar()

            return render(request, "solicitudes/enviada.html", {
                "solicitud": solicitud_datos,
                "acompanantes": acompanantes_datos,
            })

    ctx = {
        "paso": PasoSolicitud.CONFIRMACION.value,
        "reserva": reserva_info,
        "terminos": settings.TERMINOS_Y_CONDICIONES,
        "acepta_inicial": False,
        "error_terminos": error_terminos,
    }
    return render(request, "solicitudes/solicitar.html", ctx)


@login_required
def solicitar(request):
    """Formulario de solicitud de reserva en flujo multipaso (US-02).

    Paso 1: Selección de horario y bloques en el calendario de disponibilidad.
    Paso 2: Datos de la actividad (área, motivo, observaciones) y acompañantes.
    Paso 3: Revisión de la reserva, aceptación de términos y confirmación.
    """
    areas = request.user.areas.filter(activa=True)
    if not areas.exists():
        # US-05 AC4: la solicitud se vincula a un area. Sin area no hay a que
        # vincularla, y es mejor decirlo que mostrar un desplegable vacio.
        return render(request, "solicitudes/sin_area.html")

    wizard = SolicitudWizard(request.session)
    paso_solicitado = PasoSolicitud.resolver(
        request.POST.get("paso", request.GET.get("paso", 1))
    )
    paso_actual = paso_solicitado.validar_acceso(wizard.datos)

    if paso_actual == PasoSolicitud.HORARIO:
        return _manejar_paso_horario(request, wizard)
    elif paso_actual == PasoSolicitud.DATOS:
        return _manejar_paso_datos(request, wizard)
    elif paso_actual == PasoSolicitud.CONFIRMACION:
        return _manejar_paso_confirmacion(request, wizard)

    return _manejar_paso_horario(request, wizard)
