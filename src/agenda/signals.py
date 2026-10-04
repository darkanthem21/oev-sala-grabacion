"""Lo que agenda necesita de otros módulos sin depender de ellos.

Las reservas aprobadas son de `solicitudes`, que depende de agenda y no al revés
(README.md). Para saber a quién le quita la sala un bloqueo (US-17 AC4), agenda
pregunta por esta señal y contesta `solicitudes` (`services.reservas_aprobadas`).
"""
from dataclasses import dataclass
from datetime import date, time

from django.dispatch import Signal


@dataclass(frozen=True)
class Reserva:
    """Una reserva aprobada, con lo justo para avisarle a quien la pidió."""

    codigo: str
    fecha: date
    inicio: time
    termino: time
    solicitante: str
    correo: str


# Se envía con `desde` y `hasta`. Cada receptor devuelve una lista de `Reserva`
# aprobadas en esas fechas. Cuáles alcanza el bloqueo lo decide agenda, porque
# la regla de qué cubre un bloqueo es suya.
reservas_aprobadas = Signal()
