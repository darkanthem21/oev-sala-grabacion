"""US-07: de donde salen los datos del panel del validador.

POR AHORA SON DE PRUEBA. Todo lo que muestra el panel se lee de
`datos_prueba/panel_validador.json`, no de PostgreSQL. Todavia no existen las
tablas de Solicitud ni de Ticket: cual de las dos guarda el estado de la
validacion es la decision abierta del modelo de datos (tarea 2 de US-07).

Cuando exista el modelo, se reemplaza `cargar` por la consulta a la base y se
devuelve la misma forma de datos; la plantilla no se entera del cambio.
"""
import json
from pathlib import Path

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
