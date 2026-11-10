"""Persistencia de reportes de check-out y sus evidencias."""

from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .models import Checkout, EdicionCheckout, FotoIntegridad, RespuestaCheckout


@transaction.atomic
def guardar_reporte(ticket, listado, datos, usuario, *, asistio=True, registro=None):
    """Registra asistencia y datos validados, o una corrección dentro del plazo.

    Se copia el listado completo para que editarlo no reescriba la historia.
    Una respuesta Sí descarta cualquier evidencia residual del formulario.
    La inasistencia no crea preguntas respondidas ni requiere evidencia de cierre.
    Cada edición conserva el estado anterior y las referencias a sus fotografías.
    """
    if registro is not None:
        registro = Checkout.objects.select_for_update().get(pk=registro.pk)
        if not registro.puede_editar(usuario):
            raise PermissionDenied("Solo el autor puede editar durante los 10 minutos posteriores al registro.")
        EdicionCheckout.objects.create(checkout=registro, quien=usuario, antes={
            "asistio": registro.asistio, "respuestas": registro.respuestas,
            "hora_salida": registro.hora_salida.isoformat() if registro.hora_salida else None,
            "observaciones": registro.observaciones, "recomendaciones": registro.recomendaciones,
            "foto_final": registro.foto_final.name,
            "fotos": {foto.pregunta: foto.archivo.name for foto in registro.fotos.all()},
        })
        registro.fotos.all().delete()
        registro.respuestas_detalladas.all().delete()
        registro.editado_en = timezone.now()
        registro.editado_por = usuario
    else:
        registro = Checkout(ticket=ticket, formulario=listado.secciones, revision=listado.revision, registrado_por=usuario)
    respuestas = {}
    for seccion in listado.secciones if asistio else []:
        for pregunta in seccion["preguntas"]:
            clave = pregunta["id"]
            cumple = datos[f"respuesta_{clave}"] == "si"
            respuestas[clave] = {
                "cumple": cumple,
                "observacion": datos.get(f"observacion_{clave}", "") if not cumple else "",
            }
    registro.asistio = asistio
    registro.respuestas = respuestas
    registro.hora_salida = datos["hora_salida"] if asistio else None
    registro.observaciones = datos["observaciones"] if asistio else ""
    registro.foto_final = datos["foto_final"] if asistio else ""
    registro.recomendaciones = datos.get("recomendaciones", "") if asistio else ""
    registro.save()
    for seccion in listado.secciones if asistio else []:
        for pregunta in seccion["preguntas"]:
            clave = pregunta["id"]
            respuesta = respuestas[clave]
            detalle = RespuestaCheckout.objects.create(
                checkout=registro, pregunta=clave, texto=pregunta["texto"], seccion=seccion["titulo"],
                cumple=respuesta["cumple"], observacion=respuesta["observacion"],
            )
            if not respuesta["cumple"]:
                FotoIntegridad.objects.create(checkout=registro, respuesta=detalle, pregunta=clave, archivo=datos[f"foto_{clave}"])
    return registro


def casos_falta_integridad(checkout=None):
    """Consulta reutilizable por reportes: únicamente preguntas respondidas No."""
    casos = RespuestaCheckout.objects.faltas_integridad().select_related("checkout__ticket__solicitud", "foto")
    return casos.filter(checkout=checkout) if checkout is not None else casos


def resumen_respuestas(registro):
    """Representación común para pantalla y PDF, usando el listado original."""
    if registro is None or not registro.asistio:
        return []
    fotos = {foto.pregunta: foto for foto in registro.fotos.all()}
    secciones = []
    for seccion in registro.formulario:
        preguntas = []
        for pregunta in seccion["preguntas"]:
            respuesta = registro.respuestas.get(pregunta["id"], {})
            preguntas.append({
                **pregunta, "respondida": "cumple" in respuesta,
                "cumple": respuesta.get("cumple"), "observacion": respuesta.get("observacion", ""),
                "foto": fotos.get(pregunta["id"]),
            })
        secciones.append({"titulo": seccion["titulo"], "preguntas": preguntas})
    return secciones
