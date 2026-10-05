"""US-07: los datos del panel del validador.

`cargar` lee las solicitudes pendientes de la base y las entrega con la forma
que espera el componente de Alpine (`_validacion.html`), así la plantilla no
sabe de modelos.
"""
from datetime import date, time, timedelta

from django.utils import timezone

from agenda.models import Bloque, Dia, bloqueos_por_fecha
from personas.models import Area

from .models import Solicitud


def _bloques(s):
    return [
        {
            "ticket": sb.ticket,
            "fecha": s.fecha.isoformat(),
            "dia": Dia(s.fecha.weekday()).label,
            "inicio": f"{sb.bloque.inicio:%H:%M}",
            "termino": f"{sb.bloque.termino:%H:%M}",
        }
        for sb in s.solicitudes_bloques.all()
    ]


def cargar(hoy=None):
    """Las solicitudes pendientes desde hoy, con sus áreas y bloques (AC1).

    Forma: {"jornada", "areas", "solicitudes"}. Cada bloque trae su fecha: el
    Bloque de agenda es una plantilla semanal sin fecha. Una pendiente sin
    bloques no se muestra: no hay nada que resolver y la grilla no tendría
    semana.
    """
    hoy = hoy or timezone.localdate()
    solicitudes = (
        Solicitud.objects
        .filter(estado_validacion=Solicitud.EstadoValidacion.PENDIENTE, fecha__gte=hoy,
                solicitudes_bloques__isnull=False)
        .distinct()
        .con_detalle()
        .select_related("solicitante")
        .prefetch_related("acompanantes")
        .order_by("fecha", "id")
    )
    jornada = sorted({(b.inicio, b.termino) for b in Bloque.objects.filter(activo=True)})
    return {
        "jornada": [{"inicio": f"{i:%H:%M}", "termino": f"{t:%H:%M}"} for i, t in jornada],
        "areas": [{"id": a.pk, "nombre": a.nombre, "prioridad": a.prioridad} for a in Area.objects.all()],
        "solicitudes": [
            {
                "id": s.pk,
                "encargado": {
                    "nombre": s.solicitante.get_full_name() or s.solicitante.email,
                    "correo": s.solicitante.email,
                },
                "area": s.area_id,
                "motivo": s.motivo,
                "observaciones": s.observaciones,
                "personas": s.personas,
                "acompanantes": [{"nombre": a.nombre, "correo": a.correo} for a in s.acompanantes.all()],
                "enviada": timezone.localtime(s.creado_en).strftime("%Y-%m-%dT%H:%M"),
                "bloques": _bloques(s),
            }
            for s in solicitudes
        ],
    }


def marcar_bloqueos(datos):
    """US-17 AC2 y AC3: qué horarios de las semanas del panel están bloqueados.

    Va aparte de `cargar` porque consulta la base, y los datos de prueba se
    revisan sin ella. Los bloqueos sí son reales. Agrega `bloqueados`, que es
    {"AAAA-MM-DD HH:MM": motivo} con la misma clave que usa la pantalla para
    cada pedido, y cubre las semanas completas porque el cuadro las dibuja
    enteras.
    """
    fechas = [date.fromisoformat(b["fecha"]) for s in datos["solicitudes"] for b in s["bloques"]]
    datos["bloqueados"] = {}
    if not fechas:
        return datos
    desde = min(fechas) - timedelta(days=min(fechas).weekday())
    hasta = max(fechas) + timedelta(days=6 - max(fechas).weekday())
    horas = [time.fromisoformat(h["inicio"]) for h in datos["jornada"]]
    for fecha, bloqueos in bloqueos_por_fecha(desde, hasta).items():
        for hora in horas:
            bloqueo = next((b for b in bloqueos if b.cubre(fecha, hora)), None)
            if bloqueo is not None:
                datos["bloqueados"][f"{fecha:%Y-%m-%d} {hora:%H:%M}"] = bloqueo.razon
    return datos
