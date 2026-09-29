from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from personas.models import Area


class Solicitud(models.Model):
    """Representa la solicitud de reserva de la sala de grabación (US-02)."""

    class EstadoValidacion(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACEPTADA = "ACEPTADA", "Aceptada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    class EstadoConfirmacion(models.TextChoices):
        NO_HABILITADA = "NO_HABILITADA", "No habilitada"
        PENDIENTE = "PENDIENTE", "Pendiente"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        CANCELADA = "CANCELADA", "Cancelada"
    # "No habilitada" es el estado inicial de la confirmación, cuando la solicitud aún no
    # ha sido aceptada por el validador.

    # Si ha sido aceptada por el validador, sigue "No habilitada" si todavía no se entra 
    # en la ventana de 48 horas.

    # Cambia a "Pendiente" cuando se envía la notificación de confirmación al solicitante.

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitudes",
        verbose_name="solicitante",
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="solicitudes",
        verbose_name="área académica",
    )
    motivo = models.CharField(
        max_length=300,
        verbose_name="motivo de la solicitud",
    )
    estado_validacion = models.CharField(
        max_length=20,
        choices=EstadoValidacion.choices,
        default=EstadoValidacion.PENDIENTE,
        verbose_name="estado de validación",
    )
    estado_confirmacion = models.CharField(
        max_length=20,
        choices=EstadoConfirmacion.choices,
        default=EstadoConfirmacion.NO_HABILITADA,
        verbose_name="estado de confirmación",
    )

    @property
    def total_personas(self):
        """Total de personas en sala: solicitante (1) + acompañantes registrados."""
        if self.pk:
            return 1 + self.acompanantes.count()
        return 1

    @property
    def estado_general(self):
        """Síntesis de alto nivel del estado de la solicitud para vistas."""
        if self.estado_validacion == self.EstadoValidacion.PENDIENTE:
            return "En revisión por la Oficina"
        if self.estado_validacion == self.EstadoValidacion.RECHAZADA:
            return "Rechazada"
        if self.estado_confirmacion == self.EstadoConfirmacion.CONFIRMADA:
            return "Confirmada"
        if self.estado_confirmacion == self.EstadoConfirmacion.CANCELADA:
            return "Cancelada"
        if self.estado_confirmacion == self.EstadoConfirmacion.PENDIENTE:
            return "Pendiente de confirmación"
        return "Aceptada"

    def clean(self):
        super().clean()
        total = self.total_personas

        # Validar restricción total_personas a 1-5
        MinValueValidator(1)(total)
        MaxValueValidator(5)(total)

        if self.estado_validacion != self.EstadoValidacion.ACEPTADA:
            if self.estado_confirmacion == self.EstadoConfirmacion.CONFIRMADA:
                raise ValidationError({
                    "estado_confirmacion": "No se puede confirmar una solicitud que no ha sido aceptada por el validador."
                })
            if self.estado_confirmacion == self.EstadoConfirmacion.PENDIENTE:
                raise ValidationError({
                    "estado_confirmacion": "La confirmación solo puede estar pendiente si la solicitud fue aceptada por el validador."
                })

    bloques = models.ManyToManyField(
        "agenda.Bloque",
        through="SolicitudBloque",
        related_name="solicitudes",
        verbose_name="bloques solicitados",
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="última actualización")

    class Meta:
        verbose_name = "solicitud de reserva"
        verbose_name_plural = "solicitudes de reserva"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Solicitud #{self.pk} - {self.solicitante} (Val: {self.get_estado_validacion_display()} / Conf: {self.get_estado_confirmacion_display()})"


class SolicitudBloque(models.Model):
    """Tabla intermedia explícita entre Solicitud de reserva y Bloque."""

    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name="solicitudes_bloques",
        verbose_name="solicitud",
    )
    bloque = models.ForeignKey(
        "agenda.Bloque",
        on_delete=models.PROTECT,
        related_name="solicitudes_bloques",
        verbose_name="bloque",
    )

    class Meta:
        verbose_name = "bloque de solicitud"
        verbose_name_plural = "bloques de solicitudes"
        constraints = [
            models.UniqueConstraint(
                fields=["solicitud", "bloque"],
                name="solicitud_bloque_unica",
            )
        ]

    def __str__(self):
        return f"Solicitud #{self.solicitud_id} - Bloque #{self.bloque_id}"


class Acompanante(models.Model):
    """Identificación de acompañantes en sala para la solicitud (US-02 AC6)."""

    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name="acompanantes",
        verbose_name="solicitud",
    )
    nombre = models.CharField(max_length=120, verbose_name="nombre")
    correo = models.EmailField(verbose_name="correo electrónico")

    class Meta:
        verbose_name = "acompañante"
        verbose_name_plural = "acompañantes"

    def __str__(self):
        return f"{self.nombre} ({self.correo})"
