from collections import defaultdict
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from configuracion.models import Parametros


class Dia(models.IntegerChoices):
    LUNES = 0, "lunes"
    MARTES = 1, "martes"
    MIERCOLES = 2, "miércoles"
    JUEVES = 3, "jueves"
    VIERNES = 4, "viernes"


def minutos(hora):
    return hora.hour * 60 + hora.minute


class Bloque(models.Model):
    """Un tramo de la plantilla semanal, sin fecha.

    La jornada se define una vez y se repite todas las semanas. Suspender fechas
    concretas es `bloqueo` (US-17). La colación no está modelada: es el hueco
    entre dos bloques.
    """

    dia = models.PositiveSmallIntegerField("día", choices=Dia)
    inicio = models.TimeField()
    termino = models.TimeField("término")
    # US-04 AC3: un bloque nunca se borra. Desactivarlo lo saca de la jornada y
    # las solicitudes que ya lo apuntan siguen resolviendo.
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["dia", "inicio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(termino__gt=F("inicio")),
                name="bloque_termina_despues_de_empezar",
            ),
            # Parcial porque un bloque quitado sigue en la tabla y su hora
            # tiene que quedar libre.
            models.UniqueConstraint(
                fields=["dia", "inicio"],
                condition=Q(activo=True),
                name="bloque_unico_por_dia_y_hora",
            ),
        ]

    def __str__(self):
        return f"{self.get_dia_display()} {self.inicio:%H:%M}–{self.termino:%H:%M}"

    @property
    def dura(self):
        return minutos(self.termino) - minutos(self.inicio)

    def cruce(self):
        """El bloque activo con el que se pisa, si hay alguno.

        Devuelve el bloque para que la pantalla pueda señalarlo. Un error que
        dice cuál es el otro se arregla solo.
        """
        if self.inicio is None or self.termino is None or self.termino <= self.inicio:
            return None
        return (
            Bloque.objects.filter(
                activo=True, dia=self.dia, inicio__lt=self.termino, termino__gt=self.inicio
            )
            .exclude(pk=self.pk)
            .first()
        )

    def clean(self):
        """El cruce se valida acá porque declararlo en la base necesitaría una
        extensión de Postgres. El único y el check sí son declarativos."""
        if self.inicio is None or self.termino is None:
            return  # Falta una hora: eso lo reporta `clean_fields`, no este.
        if self.termino <= self.inicio:
            raise ValidationError({"termino": "El bloque tiene que terminar después de empezar."})
        otro = self.cruce()
        if otro is not None:
            raise ValidationError(
                f"Se cruza con el bloque de {otro.inicio:%H:%M} a {otro.termino:%H:%M}."
            )


def plantilla_semanal():
    """Los bloques activos agrupados por día de la semana. Uno desactivado ya no
    es parte de la jornada."""
    por_dia = defaultdict(list)
    for bloque in Bloque.objects.filter(activo=True):
        por_dia[bloque.dia].append(bloque)
    return por_dia


def disponibilidad(desde, hasta):
    """Qué bloques tiene cada fecha del rango, ambos extremos incluidos.

    La jornada se define por día de la semana y las reservas se piden por fecha.
    Esta función es la traducción entre las dos y el único lugar donde ocurre.
    Los bloqueos puntuales (US-17) se van a descontar acá dentro.

    Devuelve {fecha: [bloques]}. Una fecha sin jornada no aparece.
    """
    plantilla = plantilla_semanal()
    dias = {}
    fecha = desde
    while fecha <= hasta:
        bloques = plantilla.get(fecha.weekday())
        if bloques:
            dias[fecha] = bloques
        fecha += timedelta(days=1)
    return dias


def primera_fecha_pedible(ahora=None):
    """El lunes de la primera semana para la que se puede pedir.

    Entre la solicitud y la fecha pedida tienen que pasar semanas completas
    (`semanas_desfase`). Pasado el límite semanal la cuenta corre una semana más:
    quien pide el viernes a las 11:00 ya pide para la semana siguiente a la que
    alcanzaba a las 09:00.

    Se cuenta en semanas para que la fecha más cercana caiga siempre en lunes y
    el validador reciba la semana completa de una vez.
    """
    parametros = Parametros.cargar()
    ahora = timezone.localtime(ahora)
    lunes = ahora.date() - timedelta(days=ahora.weekday())
    corte = timezone.make_aware(
        datetime.combine(lunes + timedelta(days=parametros.pedir_dia), parametros.pedir_hora)
    )
    semanas = 1 + parametros.semanas_desfase + (1 if ahora > corte else 0)
    return lunes + timedelta(weeks=semanas)
