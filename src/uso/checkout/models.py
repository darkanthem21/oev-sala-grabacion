"""Listado configurable, reportes y evidencias del check-out."""

from django.conf import settings
from django.db import models


def listado_inicial():
    return [
        {"id": "integridad", "titulo": "Estado e integridad", "preguntas": [
            {"id": "paredes", "texto": "¿Las paredes y paneles acústicos están sin daños?"},
            {"id": "puerta", "texto": "¿La puerta y los sellos acústicos funcionan correctamente?"},
        ]},
        {"id": "limpieza", "titulo": "Orden y limpieza", "preguntas": [
            {"id": "basura", "texto": "¿La sala está sin basura ni objetos personales?"},
            {"id": "mobiliario", "texto": "¿El mobiliario está en su posición original?"},
        ]},
        {"id": "equipamiento", "titulo": "Equipamiento técnico", "preguntas": [
            {"id": "cables", "texto": "¿Los micrófonos y cables están guardados y enrollados?"},
            {"id": "apagado", "texto": "¿La consola y los periféricos están apagados?"},
            {"id": "equipos", "texto": "¿Los equipos y cables están sin daños ni faltantes?"},
        ]},
        {"id": "cumplimiento", "titulo": "Cumplimiento del horario", "preguntas": [
            {"id": "ingreso", "texto": "¿El ingreso se realizó a la hora prevista?"},
            {"id": "desocupacion", "texto": "¿La sala se desocupó a la hora prevista?"},
        ]},
    ]


class FormularioCheckout(models.Model):
    secciones = models.JSONField(default=listado_inicial)
    revision = models.PositiveIntegerField(default=1)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actualizado_en = models.DateTimeField(auto_now=True)

    @classmethod
    def cargar(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Checkout(models.Model):
    ticket = models.OneToOneField("solicitudes.SolicitudBloque", on_delete=models.PROTECT, related_name="reporte_checkout")
    formulario = models.JSONField()
    revision = models.PositiveIntegerField()
    respuestas = models.JSONField()
    hora_salida = models.TimeField()
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    registrado_en = models.DateTimeField(auto_now_add=True)


class FotoIntegridad(models.Model):
    checkout = models.ForeignKey(Checkout, on_delete=models.CASCADE, related_name="fotos")
    pregunta = models.CharField(max_length=64)
    archivo = models.ImageField(upload_to="checkout/%Y/%m/%d/")
