"""US-14: qué bloques ve el personal de apoyo.

POR AHORA LOS DATOS SON DE PRUEBA. Se leen de `datos_prueba/bloques_apoyo.json`,
no de PostgreSQL, porque todavía no existen las tablas de Solicitud ni de Ticket.
Cuando existan, se reemplaza `_tickets` por la consulta a la base y se devuelve
la misma forma; la vista y la plantilla no se enteran.

AC7 quedó decidido así: todos los del personal de apoyo ven todos los bloques del
día. Es el supuesto del equipo ("siempre hay personal de apoyo, no se modela su
disponibilidad") y el modelo de datos no tiene a quién asignarlos.
"""
import json
from datetime import datetime, time, timedelta
from pathlib import Path

from django.utils import timezone

ORIGEN = "prueba"
RUTA = Path(__file__).resolve().parent / "datos_prueba" / "bloques_apoyo.json"

# AC4: una pendiente todavía puede rechazarse, así que no hay a quién esperar.
# AC5: la cancelada se lista marcada en vez de desaparecer, para que nadie se
# quede esperando a alguien que ya avisó que no viene.
VISIBLES = {"aprobada", "confirmada", "cancelada"}


def _tickets():
    hoy = timezone.localdate()
    with RUTA.open(encoding="utf-8") as archivo:
        tickets = json.load(archivo)["tickets"]
    return [{**t, "fecha": hoy + timedelta(days=t["en_dias"])} for t in tickets]


def _armar(t, enviados, ahora):
    """El ticket con su estado de check-out resuelto (AC6).

    `checkout` es "completado", "pendiente" si el bloque ya terminó y le falta, o
    None si todavía no termina o se canceló: en esos dos casos no hay nada que
    revisar en la sala.
    """
    inicio, termino = time.fromisoformat(t["inicio"]), time.fromisoformat(t["termino"])
    termino_en = timezone.make_aware(datetime.combine(t["fecha"], termino))
    if t["checkout"] or t["ticket"] in enviados:
        checkout = "completado"
    elif t["estado"] != "cancelada" and termino_en <= ahora:
        checkout = "pendiente"
    else:
        checkout = None
    return {**t, "inicio": inicio, "termino": termino, "checkout": checkout}


def bloques_del_dia(fecha, enviados=(), ahora=None):
    """Los bloques de esa fecha que le importan al personal de apoyo.

    `enviados` son los códigos de ticket con check-out registrado fuera del JSON.
    """
    ahora = timezone.localtime(ahora)
    bloques = [
        _armar(t, enviados, ahora)
        for t in _tickets()
        if t["fecha"] == fecha and t["estado"] in VISIBLES
    ]
    # AC1: en el orden en que van a llegar.
    return sorted(bloques, key=lambda b: b["inicio"])


def buscar(codigo, enviados=(), ahora=None):
    """Un ticket visible por su código, o None."""
    ahora = timezone.localtime(ahora)
    for t in _tickets():
        if t["ticket"] == codigo and t["estado"] in VISIBLES:
            return _armar(t, enviados, ahora)
    return None
