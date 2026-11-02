"""Listado configurable, reportes y evidencias del check-out."""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


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
    asistio = models.BooleanField(default=True)
    hora_salida = models.TimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    foto_final = models.ImageField(upload_to="checkout/cierre/%Y/%m/%d/", blank=True)
    recomendaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    registrado_en = models.DateTimeField(auto_now_add=True)
    editado_en = models.DateTimeField(null=True, blank=True)
    editado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="checkouts_editados")

    class Meta:
        indexes = [models.Index(fields=["-registrado_en", "-id"], name="checkout_historial_fecha_idx")]

    @property
    def limite_edicion(self):
        return self.registrado_en + timedelta(minutes=10)

    def puede_editar(self, usuario, ahora=None):
        return bool(
            usuario.is_authenticated and self.registrado_por_id == usuario.pk
            and (ahora or timezone.now()) <= self.limite_edicion
        )


class EdicionCheckout(models.Model):
    """Estado anterior de cada corrección, incluyendo referencias a sus fotos."""

    checkout = models.ForeignKey(Checkout, on_delete=models.CASCADE, related_name="ediciones")
    antes = models.JSONField()
    quien = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    cuando = models.DateTimeField(auto_now_add=True)


class RespuestaCheckoutQuerySet(models.QuerySet):
    def faltas_integridad(self):
        return self.filter(cumple=False, checkout__asistio=True)


class RespuestaCheckout(models.Model):
    """Pregunta y sección originales para consultar incidencias sin analizar JSON."""

    checkout = models.ForeignKey(Checkout, on_delete=models.CASCADE, related_name="respuestas_detalladas")
    pregunta = models.CharField(max_length=64)
    texto = models.CharField(max_length=500)
    seccion = models.CharField(max_length=160)
    cumple = models.BooleanField(db_index=True)
    observacion = models.TextField(blank=True)
    # Campo histórico: no se solicita ni se escribe en reportes nuevos.
    recomendacion = models.TextField(blank=True)

    objects = RespuestaCheckoutQuerySet.as_manager()

    class Meta:
        ordering = ["pk"]
        constraints = [models.UniqueConstraint(fields=["checkout", "pregunta"], name="respuesta_unica_checkout_pregunta")]


class FotoIntegridad(models.Model):
    checkout = models.ForeignKey(Checkout, on_delete=models.CASCADE, related_name="fotos")
    pregunta = models.CharField(max_length=64)
    archivo = models.ImageField(upload_to="checkout/%Y/%m/%d/")
    respuesta = models.OneToOneField(RespuestaCheckout, null=True, blank=True, on_delete=models.CASCADE, related_name="foto")
