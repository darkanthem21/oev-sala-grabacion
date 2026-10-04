"""US-07: de donde salen los datos del panel del validador.

POR AHORA SON DE PRUEBA. Todo lo que muestra el panel se lee de
`datos_prueba/panel_validador.json`, no de PostgreSQL. Todavia no existen las
tablas de Solicitud ni de Ticket: cual de las dos guarda el estado de la
validacion es la decision abierta del modelo de datos (tarea 2 de US-07).

Cuando exista el modelo, se reemplaza `cargar` por la consulta a la base y se
devuelve la misma forma de datos; la plantilla no se entera del cambio.
"""
import json
from datetime import date, time, timedelta
from pathlib import Path

from agenda.models import bloqueos_por_fecha

ORIGEN = "prueba"
RUTA = Path(__file__).resolve().parent / "datos_prueba" / "panel_validador.json"


def cargar():
    """Las solicitudes pendientes, con sus areas y bloques.

    Forma: {"areas": [...], "solicitudes": [...]}. Cada solicitud trae todos sus
    bloques pedidos, y cada bloque su fecha: el Bloque de agenda es una plantilla
    semanal sin fecha, asi que la fecha viaja con el pedido.
    """
    with RUTA.open(encoding="utf-8") as archivo:
        return json.load(archivo)


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
