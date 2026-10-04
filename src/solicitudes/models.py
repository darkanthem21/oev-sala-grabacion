from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Max, Min, Prefetch, Q

from agenda.models import Bloque, primera_fecha_pedible
from personas.models import Area


class SolicitudQuerySet(models.QuerySet):
    """Consultas del historial (US-09): qué es próxima, qué es anterior y en qué orden.

    Viven acá y no en la vista porque son reglas del dominio: los recordatorios
    de confirmación y la bandeja del validador van a necesitar la misma idea
    de "próxima".
    """

    def de(self, usuario):
        return self.filter(solicitante=usuario)

    def _con_fechas(self):
        # La primera y la última fecha de sus bloques, en la misma consulta:
        # filtrar y ordenar no necesita traer los bloques.
        return self.annotate(
            primera_fecha=Min("solicitudes_bloques__fecha"),
            ultima_fecha=Max("solicitudes_bloques__fecha"),
        )

    def proximas(self, hoy):
        """Le queda algún bloque de hoy en adelante, aunque la hora de hoy ya
        haya pasado: se separa por día calendario. La más cercana primero."""
        return (
            self._con_fechas()
            .filter(Q(ultima_fecha__gte=hoy) | Q(ultima_fecha__isnull=True))
            # El id desempata, sin un orden total, una fila podría repetirse o
            # saltarse entre páginas.
            .order_by(F("primera_fecha").asc(nulls_last=True), "id")
        )

    def anteriores(self, hoy):
        """Todos sus bloques ya pasaron. La más reciente primero."""
        return self._con_fechas().filter(ultima_fecha__lt=hoy).order_by("-ultima_fecha", "-id")

    def con_detalle(self):
        """Con lo que dibuja la tabla: el área y los bloques con su hora, en
        dos consultas para toda la página."""
        return self.select_related("area").prefetch_related(Prefetch(
            "solicitudes_bloques",
            queryset=SolicitudBloque.objects.select_related("bloque").order_by("fecha", "bloque__inicio"),
        ))


class Solicitud(models.Model):
    """Representa la solicitud de reserva de la sala de grabación (US-02)."""

    class EstadoValidacion(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACEPTADA = "ACEPTADA", "Aceptada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        # La retiró quien la pidió antes de que el validador decidiera (US-09).
        RETIRADA = "RETIRADA", "Retirada"

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

    bloques = models.ManyToManyField(
        "agenda.Bloque",
        through="SolicitudBloque",
        related_name="solicitudes",
        verbose_name="bloques solicitados",
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="última actualización")

    objects = SolicitudQuerySet.as_manager()

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

    # Etiqueta de cada estado general; la clave sirve de clase CSS en las vistas.
    ESTADOS_GENERALES = {
        "revision": "En revisión por la Oficina",
        "retirada": "Retirada",
        "rechazada": "Rechazada",
        "confirmada": "Confirmada",
        "cancelada": "Cancelada",
        "por-confirmar": "Pendiente de confirmación",
        "aceptada": "Aceptada",
    }

    @property
    def estado_clave(self):
        """Clave del estado general, combinando validación y confirmación."""
        if self.estado_validacion == self.EstadoValidacion.PENDIENTE:
            return "revision"
        if self.estado_validacion == self.EstadoValidacion.RETIRADA:
            return "retirada"
        if self.estado_validacion == self.EstadoValidacion.RECHAZADA:
            return "rechazada"
        if self.estado_confirmacion == self.EstadoConfirmacion.CONFIRMADA:
            return "confirmada"
        if self.estado_confirmacion == self.EstadoConfirmacion.CANCELADA:
            return "cancelada"
        if self.estado_confirmacion == self.EstadoConfirmacion.PENDIENTE:
            return "por-confirmar"
        return "aceptada"

    @property
    def puede_retirarse(self):
        """Solo mientras la Oficina no la haya revisado (ver services.retirar_solicitud)."""
        return self.estado_validacion == self.EstadoValidacion.PENDIENTE

    @property
    def estado_general(self):
        """Síntesis de alto nivel del estado de la solicitud para vistas."""
        return self.ESTADOS_GENERALES[self.estado_clave]

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
            # Cancelar es parte del flujo de confirmación. Solo se
            # cancela si la solicitud fue previamente aceptada.
            if self.estado_confirmacion == self.EstadoConfirmacion.CANCELADA:
                raise ValidationError({
                    "estado_confirmacion": "Solo se puede cancelar una solicitud aceptada por el validador."
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
            fecha_minima = primera_fecha_pedible()
            if self.fecha < fecha_minima:
                raise ValidationError({
                    "fecha": (
                        f"No se puede solicitar una reserva para el {self.fecha}. "
                        f"Las reservas deben realizarse a partir del lunes {fecha_minima.strftime('%d/%m/%Y')}."
                    )
                })

            if not self.bloque.activo:
                raise ValidationError({
                    "bloque": f"El bloque #{self.bloque_id} ya no se encuentra activo."
                })

            if self.bloque.dia != self.fecha.weekday():
                raise ValidationError({
                    "fecha": "El día de la semana no coincide con el turno configurado del bloque."
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
                    "bloque": f"El bloque #{self.bloque_id} ya se encuentra reservado para la fecha {self.fecha}."
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
                        "bloque": f"Ya tienes una solicitud pendiente para el bloque #{self.bloque_id} en la fecha {self.fecha}."
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
