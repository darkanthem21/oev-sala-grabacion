"""US-07: los datos del panel del validador.

`cargar` lee de la base lo que dibuja la agenda y lo entrega con la forma que
espera el componente de Alpine (`_validacion.html`), así la plantilla no sabe
de modelos. La agenda es la Jornada semanal de Configuración: cada día con sus
propios bloques, y las solicitudes dentro de ellos.
"""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from agenda.models import JORNADA_MINIMA, Bloque, bloqueos_por_fecha
from personas.models import Area

from .models import Solicitud


def _lunes(fecha):
    return fecha - timedelta(days=fecha.weekday())


def _nombre(usuario):
    return usuario.get_full_name() or usuario.email


def _bloqueos(bloques, desde, hasta):
    """US-17 AC2 y AC3: qué bloques están bloqueados en qué fecha, con la razón.

    Pregunta por la hora del bloque (`Bloqueo.cubre`), igual que al aprobar, así
    un bloqueo de día entero alcanza a todos los de esa fecha.
    """
    por_dia = defaultdict(list)
    for bloque in bloques:
        por_dia[bloque.dia].append(bloque)
    marcados = []
    for fecha, del_dia in bloqueos_por_fecha(desde, hasta).items():
        for bloque in por_dia[fecha.weekday()]:
            bloqueo = next((b for b in del_dia if b.cubre(fecha, bloque.inicio)), None)
            if bloqueo is not None:
                marcados.append({"fecha": f"{fecha:%Y-%m-%d}", "bloque": bloque.pk, "razon": bloqueo.razon})
    return marcados


def cargar(hoy=None):
    """Lo pendiente desde hoy, lo ya aprobado, la jornada de esas semanas (AC1) y
    lo resuelto hoy (AC5).

    Las semanas van de la actual a la última con pendientes. Un tope es la misma
    fecha y el mismo bloque, por id y no por hora, porque cada día tiene su
    jornada. Van también los bloques quitados: una solicitud puede apuntar a uno
    que el administrador sacó después, y la pantalla lo dibuja solo si esa fecha
    tiene algo. Una pendiente sin bloques no se muestra: no hay nada que resolver.
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
    bloques = list(Bloque.objects.order_by("dia", "inicio"))
    return {
        "ventana": list(JORNADA_MINIMA),
        "semanas": [f"{lunes:%Y-%m-%d}" for lunes in semanas],
        "bloques": [
            {"id": b.pk, "dia": b.dia, "inicio": f"{b.inicio:%H:%M}", "termino": f"{b.termino:%H:%M}",
             "activo": b.activo}
            for b in bloques
        ],
        "areas": [
            {"id": a.pk, "nombre": a.nombre, "prioridad": a.prioridad, "nota": a.nota} for a in Area.objects.all()
        ],
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
        "bloqueos": _bloqueos(bloques, primera, hasta),
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
