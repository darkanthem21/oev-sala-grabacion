from datetime import time

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.dates import WEEKDAYS

# Los nombres ya traducidos que trae Django. Importar `agenda.Dia` sería una
# dependencia al revés, y `configuracion` no depende de nadie (README.md).
DIAS_HABILES = [(n, WEEKDAYS[n]) for n in range(5)]


class Parametros(models.Model):
    """Los umbrales con los que opera el sistema. Una sola fila.

    Cada campo trae el valor por defecto que fijó el cliente (AC2). El parámetro
    se lee al resolver una solicitud nueva, así que cambiarlo no toca las ya
    enviadas (AC3).

    No llevan `help_text`: lo que hace cada umbral lo dice su descripción en
    `forms.SECCIONES`, y escrito en dos lugares terminaría diciendo dos cosas.
    """

    pedir_dia = models.PositiveSmallIntegerField(
        "día límite para pedir", choices=DIAS_HABILES, default=4
    )
    pedir_hora = models.TimeField("hora límite para pedir", default=time(10, 0))
    # La anticipación mínima del AC1. Vuelve medida en semanas completas para que
    # la fecha más cercana caiga siempre en lunes y el validador tenga la semana
    # entera para revisar.
    semanas_desfase = models.PositiveSmallIntegerField(
        "desfase mínimo", default=1,
        validators=[MinValueValidator(0), MaxValueValidator(8)],
    )

    plazo_confirmacion_dias = models.PositiveSmallIntegerField(
        "plazo de confirmación previa", default=2,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
    )
    # Los dos topes marcan la solicitud, no la impiden (arquitectura.md §5.2).
    tope_mensual = models.PositiveSmallIntegerField(
        "tope mensual por usuario", default=8,
        validators=[MinValueValidator(1), MaxValueValidator(40)],
    )
    max_bloques_solicitud = models.PositiveSmallIntegerField(
        "bloques por solicitud", default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )

    # Decisión 17: la sanción corre sola y el administrador la gestiona después.
    inasistencias_para_sancion = models.PositiveSmallIntegerField(
        "inasistencias para penalizar", default=2,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    dias_sancion = models.PositiveSmallIntegerField(
        "duración de la sanción", default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
    )

    # Estaban en `settings`, pero el RNF 1 pide cambiarlos sin redesplegar.
    intentos_maximos = models.PositiveSmallIntegerField(
        "intentos antes de bloquear", default=5,
        validators=[MinValueValidator(3), MaxValueValidator(20)],
    )
    minutos_bloqueo = models.PositiveSmallIntegerField(
        "duración del bloqueo por intentos", default=15,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
    )

    # AC5: el cliente lo edita sin recompilar. Este texto es provisorio, el real
    # lo redacta la Oficina de Educación Virtual.
    terminos = models.TextField(
        "términos y condiciones", blank=True,
        default=(
            "La sala de grabación es un recurso compartido de la Oficina de Educación Virtual.\n"
            "Quien solicita se compromete a: presentarse puntualmente en el bloque reservado; "
            "usar la sala solo para la actividad declarada en el motivo; no exceder la cantidad "
            "de personas declarada; dejar el equipamiento y el mobiliario en el estado en que los "
            "encontró; y avisar con anticipación si no va a ocupar la reserva.\n"
            "El incumplimiento queda registrado en el check-out y puede derivar en una sanción "
            "que suspende temporalmente la posibilidad de pedir nuevas reservas."
        ),
    )

    class Meta:
        verbose_name = "parámetros del sistema"
        verbose_name_plural = "parámetros del sistema"

    def __str__(self):
        return "Parámetros del sistema"

    def save(self, *args, **kwargs):
        # Una sola fila: un `Parametros()` suelto crearía otra y el sistema
        # tendría dos configuraciones distintas.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def cargar(cls):
        """Los parámetros vigentes, creando la fila con los valores por defecto
        si no existe. Es el único punto de entrada; nadie hace `objects.get`."""
        return cls.objects.get_or_create(pk=1)[0]


class CambioParametro(models.Model):
    """AC4: quién cambió qué valor, de cuánto a cuánto y cuándo."""

    campo = models.CharField(max_length=50)
    antes = models.TextField()
    despues = models.TextField()
    # SET_NULL porque la bitácora no puede impedir dar de baja a un
    # administrador, ni desaparecer con él.
    quien = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cambios_de_configuracion",
    )
    cuando = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cuando"]
        verbose_name = "cambio de configuración"
        verbose_name_plural = "cambios de configuración"

    def __str__(self):
        return f"{self.etiqueta}: {self.antes} → {self.despues}"

    @property
    def etiqueta(self):
        try:
            return Parametros._meta.get_field(self.campo).verbose_name
        except FieldDoesNotExist:
            # Un parámetro que se quitó del modelo sigue en la bitácora. Vale
            # más su nombre crudo que perder la fila.
            return self.campo
