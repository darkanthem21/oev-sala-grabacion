"""Lo que agenda necesita de otros módulos sin depender de ellos.

Las solicitudes son de `solicitudes`, que depende de agenda y no al revés
(README.md). Cuando agenda saca horario (bloquear, quitar o cambiar un bloque),
pregunta por `pedidos_vivos` a quién le quita la sala y anuncia con
`horario_quitado` lo que se confirmó. Las dos las contesta `solicitudes`
(`services.pedidos_vivos` y `services.liberar`).
"""
from dataclasses import dataclass
from datetime import date, time

from django.dispatch import Signal


@dataclass(frozen=True)
class Pedido:
    """Un bloque que pide una solicitud viva, con lo justo para saber si un
    corte lo alcanza y avisarle a quien lo pidió."""

    solicitud: int
    codigo: str
    fecha: date
    bloque: int
    inicio: time
    termino: time
    pendiente: bool
    solicitante: str
    correo: str


# Se envía con `desde`, `hasta` (None es sin tope) y, si se quiere, `bloque` (un
# id). Cada receptor devuelve una lista de `Pedido` de solicitudes pendientes o
# aprobadas sin cancelar. Cuáles alcanza el corte lo decide agenda, porque la
# regla de qué cubre un bloqueo es suya.
pedidos_vivos = Signal()

# Se envía con `afectadas` (los `Pedido` que el administrador vio y confirmó),
# `razon` y `quien`, dentro de la transacción que guarda el corte.
horario_quitado = Signal()
