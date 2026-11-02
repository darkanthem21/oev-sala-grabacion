"""US-14: qué bloques ve el personal de apoyo.

Cada bloque de la lista es un ticket: un bloque de una solicitud aceptada en una
fecha (`SolicitudBloque`). El estado de completado se lee de `Checkout` y es
compartido por todo el personal de apoyo.

AC7 quedó decidido así: todos los del personal de apoyo ven todos los bloques del
día. Es el supuesto del equipo ("siempre hay personal de apoyo, no se modela su
disponibilidad") y el modelo de datos no tiene a quién asignarlos.
"""
from datetime import datetime
import re

from django.utils import timezone

from agenda.models import bloqueos_por_fecha
from solicitudes.models import Solicitud, SolicitudBloque
from .checkout.models import Checkout

# AC4: solo las aceptadas; una pendiente todavía puede rechazarse, así que no
# hay a quién esperar. AC5: la cancelada se lista marcada en vez de desaparecer,
# para que nadie se quede esperando a alguien que ya avisó que no viene.
ESTADOS = {
    Solicitud.EstadoConfirmacion.NO_HABILITADA: "aprobada",
    Solicitud.EstadoConfirmacion.PENDIENTE: "aprobada",
    Solicitud.EstadoConfirmacion.CONFIRMADA: "confirmada",
    Solicitud.EstadoConfirmacion.CANCELADA: "cancelada",
}


def _tickets(**filtro):
    filas = SolicitudBloque.objects.filter(
        solicitud__estado_validacion=Solicitud.EstadoValidacion.ACEPTADA, **filtro
    ).select_related("bloque", "solicitud__solicitante", "solicitud__area")
    return [
        {
            "ticket": f.ticket,
            "fecha": f.fecha,
            "inicio": f.inicio,
            "termino": f.termino,
            "solicitante": f.solicitud.solicitante.get_full_name() or f.solicitud.solicitante.email,
            "area": f.solicitud.area.nombre,
            "personas": f.solicitud.personas,
            "estado": ESTADOS[f.solicitud.estado_confirmacion],
        }
        for f in filas
    ]


def _armar(t, enviados, ahora):
    """El ticket con su estado de check-out resuelto (AC6).

    `checkout` es "completado", "pendiente" si el bloque ya terminó y le falta, o
    None si todavía no termina o se canceló: en esos dos casos no hay nada que
    revisar en la sala.
    """
    termino_en = timezone.make_aware(datetime.combine(t["fecha"], t["termino"]))
    if t["ticket"] in enviados:
        checkout = "completado"
    elif t["estado"] != "cancelada" and termino_en <= ahora:
        checkout = "pendiente"
    else:
        checkout = None
    return {**t, "checkout": checkout}


def bloques_del_dia(fecha, ahora=None):
    """Los bloques de esa fecha que le importan al personal de apoyo.

    Los check-outs completados se consultan siempre en la base de datos.
    Cada bloque trae además el bloqueo que le quitó la sala, si hay uno (US-17
    AC2), para que nadie la prepare para una grabación que no va a ocurrir.
    """
    ahora = timezone.localtime(ahora)
    enviados = {f"T-{pk:02d}" for pk in Checkout.objects.filter(ticket__solicitud__fecha=fecha).values_list("ticket_id", flat=True)}
    bloqueos = bloqueos_por_fecha(fecha, fecha).get(fecha, [])
    bloques = [_armar(t, enviados, ahora) for t in _tickets(solicitud__fecha=fecha)]
    for bloque in bloques:
        bloque["bloqueo"] = next((b for b in bloqueos if b.cubre(fecha, bloque["inicio"])), None)
    # AC1: en el orden en que van a llegar.
    return sorted(bloques, key=lambda b: b["inicio"])


def buscar(codigo, ahora=None):
    """Un ticket visible por su código («T-07»), o None."""
    coincidencia = re.fullmatch(r"T-([0-9]{2,19})", codigo)
    if coincidencia is None:
        return None
    numero = int(coincidencia.group(1))
    if not 1 <= numero <= 2**63 - 1:
        return None
    enviados = [codigo] if Checkout.objects.filter(ticket_id=numero).exists() else []
    # El código se compara entero para que «T-7» no sea otra forma de «T-07».
    t = next((t for t in _tickets(pk=numero) if t["ticket"] == codigo), None)
    return _armar(t, enviados, timezone.localtime(ahora)) if t else None
