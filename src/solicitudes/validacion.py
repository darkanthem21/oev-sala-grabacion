"""US-07: los datos del panel del validador.

`cargar` lee de la base lo que dibuja la agenda y lo entrega con la forma que
espera el componente de Alpine (`_validacion.html`), así la plantilla no sabe
de modelos. La agenda es la Jornada semanal de Configuración: cada día con sus
propios bloques, y las solicitudes dentro de ellos.
"""
from datetime import timedelta

from django.utils import timezone

from agenda.models import JORNADA_MINIMA, Bloque, bloqueos_por_fecha, disponibilidad
from personas.models import Area

from .models import Solicitud


def _lunes(fecha):
    return fecha - timedelta(days=fecha.weekday())


def _nombre(usuario):
    return usuario.get_full_name() or usuario.email


def _dias_bloqueados(desde, hasta):
    """Las fechas bloqueadas enteras, con su razón: la cabecera de esa columna
    lo dice, para que no parezca un día sin jornada (US-17)."""
    return {
        f"{fecha:%Y-%m-%d}": entero.razon
        for fecha, bloqueos in bloqueos_por_fecha(desde, hasta).items()
        if (entero := next((b for b in bloqueos if b.bloque_id is None), None))
    }


def cargar(hoy=None):
    """Lo pendiente desde hoy, lo ya aprobado, la jornada de esas semanas (AC1) y
    lo resuelto hoy (AC5).

    Las semanas van de la actual a la última con pendientes. Un tope es la misma
    fecha y el mismo bloque, por id y no por hora, porque cada fecha tiene su
    jornada. Lo quitado o bloqueado no se dibuja: al sacarlo, sus pendientes se
    rechazaron y sus aprobadas se cancelaron. Una pendiente sin bloques no se
    muestra: no hay nada que resolver.
    """
    hoy = hoy or timezone.localdate()
    # Sábado y domingo no tienen jornada: la agenda parte en la semana que viene.
    primera = _lunes(hoy) + timedelta(weeks=1 if hoy.weekday() >= 5 else 0)
    pendientes = (
        Solicitud.objects
        .filter(estado_validacion=Solicitud.EstadoValidacion.PENDIENTE, fecha__gte=hoy,
                solicitudes_bloques__isnull=False)
        .distinct()
        .con_detalle()
        .select_related("solicitante")
        .prefetch_related("acompanantes")
        .order_by("fecha", "id")
    )
    ultima = max([_lunes(s.fecha) for s in pendientes], default=primera)
    semanas = [primera + timedelta(weeks=n) for n in range((ultima - primera).days // 7 + 1)]
    hasta = semanas[-1] + timedelta(days=4)
    reservadas = (
        Solicitud.objects
        .filter(estado_validacion=Solicitud.EstadoValidacion.ACEPTADA, fecha__range=(primera, hasta))
        .exclude(estado_confirmacion=Solicitud.EstadoConfirmacion.CANCELADA)
        .con_detalle()
        .select_related("solicitante")
    )
    resueltas = (
        Solicitud.objects
        .filter(resuelta_en__date=hoy)
        .con_detalle()
        .select_related("solicitante", "resuelta_por", "asignada_a__solicitante")
        .order_by("resuelta_en", "id")
    )
    # Lo que se puede pedir cada fecha, como lo ve el asistente: sin lo quitado
    # ni lo bloqueado, con lo que es solo de esa semana.
    libres = disponibilidad(primera, hasta)
    return {
        "ventana": list(JORNADA_MINIMA),
        "semanas": [f"{lunes:%Y-%m-%d}" for lunes in semanas],
        "dias": {f"{fecha:%Y-%m-%d}": [b.pk for b in bloques] for fecha, bloques in libres.items()},
        "dias_bloqueados": _dias_bloqueados(primera, hasta),
        # Todos, también los quitados: las resueltas de hoy pueden apuntar a uno.
        # ponytail: crece con cada bloque que se agrega o mueve; filtrar por los
        # que se nombran si algún día pesa.
        "bloques": [
            {"id": b.pk, "inicio": f"{b.inicio:%H:%M}", "termino": f"{b.termino:%H:%M}"}
            for b in Bloque.objects.all()
        ],
        "areas": [{"id": a.pk, "nombre": a.nombre, "prioridad": a.prioridad} for a in Area.objects.all()],
        "solicitudes": [
            {
                "id": s.pk,
                "encargado": {"nombre": _nombre(s.solicitante)},
                "area": s.area_id,
                "motivo": s.motivo,
                "observaciones": s.observaciones,
                "personas": s.personas,
                "acompanantes": [{"nombre": a.nombre} for a in s.acompanantes.all()],
                "enviada": timezone.localtime(s.creado_en).strftime("%Y-%m-%dT%H:%M"),
                "fecha": f"{s.fecha:%Y-%m-%d}",
                "bloques": [{"ticket": sb.ticket, "bloque": sb.bloque_id} for sb in s.solicitudes_bloques.all()],
            }
            for s in pendientes
        ],
        "reservadas": [
            {"id": s.pk, "encargado": _nombre(s.solicitante), "fecha": f"{s.fecha:%Y-%m-%d}",
             "bloques": [sb.bloque_id for sb in s.solicitudes_bloques.all()]}
            for s in reservadas
        ],
        # AC5: lo resuelto hoy por cualquiera que valide, con la forma que usa
        # la pantalla para lo que se resuelve en la sesión.
        "resueltas": [
            {
                "s": {"id": s.pk, "encargado": {"nombre": _nombre(s.solicitante)}, "fecha": f"{s.fecha:%Y-%m-%d}",
                      "bloques": [{"bloque": sb.bloque_id} for sb in s.solicitudes_bloques.all()]},
                "estado": "aprobada" if s.estado_validacion == Solicitud.EstadoValidacion.ACEPTADA else "rechazada",
                "motivo": s.motivo_resolucion,
                "asignada": _nombre(s.asignada_a.solicitante) if s.asignada_a else "",
                "validador": _nombre(s.resuelta_por),
                "hora": f"{timezone.localtime(s.resuelta_en):%H:%M}",
            }
            for s in resueltas
        ],
    }
