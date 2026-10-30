"""Persistencia de reportes de check-out y sus evidencias."""

from .models import Checkout, FotoIntegridad


def guardar_reporte(ticket, listado, datos, usuario):
    """Persiste datos ya validados dentro de la transacción que bloquea el ticket.

    Se copia el listado completo para que editarlo no reescriba la historia.
    Una respuesta Sí descarta cualquier evidencia residual del formulario.
    """
    respuestas = {}
    for seccion in listado.secciones:
        for pregunta in seccion["preguntas"]:
            clave = pregunta["id"]
            cumple = datos[f"respuesta_{clave}"] == "si"
            respuestas[clave] = {
                "cumple": cumple,
                "observacion": datos.get(f"observacion_{clave}", "") if not cumple else "",
            }
    registro = Checkout.objects.create(
        ticket=ticket, formulario=listado.secciones, revision=listado.revision,
        respuestas=respuestas, hora_salida=datos["hora_salida"],
        observaciones=datos["observaciones"], registrado_por=usuario,
    )
    for clave, respuesta in respuestas.items():
        if not respuesta["cumple"]:
            FotoIntegridad.objects.create(checkout=registro, pregunta=clave, archivo=datos[f"foto_{clave}"])
    return registro
