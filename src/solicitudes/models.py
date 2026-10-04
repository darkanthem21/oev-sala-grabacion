from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from agenda.models import Bloque, bloqueo_de, primera_fecha_pedible
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
    observaciones = models.TextField(
        blank=True,
        verbose_name="observaciones y requerimientos técnicos",
    )
    personas = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="cantidad de personas en sala",
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
    # US-04: los topes no impiden enviar; marcan la solicitud para que decida el
    # validador. Se fijan al enviar (`services.marcas`), así cambiar un tope
    # después no toca las ya enviadas (AC3).
    sobre_tope_mensual = models.BooleanField(default=False, verbose_name="sobre el tope mensual")
    sobre_bloques_por_solicitud = models.BooleanField(
        default=False, verbose_name="sobre el máximo de bloques por solicitud"
    )

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


class SolicitudBloque(models.Model):
    """Tabla intermedia explícita entre Solicitud de reserva y Bloque semanal (con fecha)."""

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
    fecha = models.DateField(verbose_name="fecha de la reserva")

    class Meta:
        verbose_name = "bloque de solicitud"
        verbose_name_plural = "bloques de solicitudes"
        constraints = [
            models.UniqueConstraint(
                fields=["solicitud", "bloque", "fecha"],
                name="solicitud_bloque_fecha_unica",
            )
        ]

    def __str__(self):
        return f"Solicitud #{self.solicitud_id} - Bloque #{self.bloque_id} ({self.fecha})"

    @property
    def ticket(self):
        return f"T-{self.id:02d}"

    @property
    def inicio(self):
        return self.bloque.inicio

    @property
    def termino(self):
        return self.bloque.termino

    def clean(self):
        super().clean()
        if not self.pk and self.bloque_id and self.fecha:
            horas = f"{self.bloque.inicio:%H:%M}–{self.bloque.termino:%H:%M}"
            fecha_minima = primera_fecha_pedible()
            if self.fecha < fecha_minima:
                raise ValidationError({
                    "fecha": (
                        f"No se puede solicitar una reserva para el {self.fecha:%d/%m/%Y}. "
                        f"Las reservas deben realizarse a partir del lunes {fecha_minima.strftime('%d/%m/%Y')}."
                    )
                })

            if not self.bloque.activo:
                raise ValidationError({
                    "bloque": f"El bloque de {horas} ya no se encuentra activo."
                })

            if self.bloque.dia != self.fecha.weekday():
                raise ValidationError({
                    "fecha": "El día de la semana no coincide con el turno configurado del bloque."
                })

            # US-17 AC3: lo bloqueado no se puede pedir, aunque se haya bloqueado
            # después de elegirlo en el paso 1.
            bloqueo = bloqueo_de(self.fecha, self.bloque.inicio)
            if bloqueo is not None:
                raise ValidationError({
                    "bloque": f"El bloque de {horas} no se puede pedir: la sala está bloqueada "
                              f"{bloqueo.periodo} ({bloqueo.razon})."
                })

            ocupados = SolicitudBloque.objects.filter(
                bloque_id=self.bloque_id,
                fecha=self.fecha,
                solicitud__estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
                solicitud__estado_confirmacion__in=[
                    Solicitud.EstadoConfirmacion.NO_HABILITADA,
                    Solicitud.EstadoConfirmacion.PENDIENTE,
                    Solicitud.EstadoConfirmacion.CONFIRMADA,
                ],
            )
            if self.solicitud_id:
                ocupados = ocupados.exclude(solicitud_id=self.solicitud_id)

            if ocupados.exists():
                raise ValidationError({
                    "bloque": f"El bloque de {horas} del {self.fecha:%d/%m} ya se encuentra reservado."
                })

            if hasattr(self, "solicitud") and self.solicitud and getattr(self.solicitud, "solicitante_id", None):
                propias_pendientes = SolicitudBloque.objects.filter(
                    bloque_id=self.bloque_id,
                    fecha=self.fecha,
                    solicitud__solicitante_id=self.solicitud.solicitante_id,
                    solicitud__estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
                ).exclude(solicitud__estado_confirmacion=Solicitud.EstadoConfirmacion.CANCELADA)
                if self.solicitud_id:
                    propias_pendientes = propias_pendientes.exclude(solicitud_id=self.solicitud_id)

                if propias_pendientes.exists():
                    raise ValidationError({
                        "bloque": f"Ya tienes una solicitud pendiente para el bloque de {horas} del {self.fecha:%d/%m}."
                    })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


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
