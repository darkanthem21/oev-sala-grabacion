from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.formats import date_format

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
    concretas es `Bloqueo` (US-17). La colación no está modelada: es el hueco
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


class Motivo(models.TextChoices):
    """US-17 AC1: por qué la sala no está."""

    MANTENCION = "mantencion", "mantención"
    FERIADO = "feriado", "feriado"
    EVENTO = "evento", "evento"


class BloqueoQuerySet(models.QuerySet):
    def vigentes(self):
        """Los que no se han levantado. Uno levantado sigue en la tabla, porque
        es el registro de lo que pasó (US-17 AC6)."""
        return self.filter(levantado_en__isnull=True)

    def entre(self, desde, hasta):
        """Los que tocan algún día del rango, ambos extremos incluidos."""
        return self.filter(desde__lte=hasta, hasta__gte=desde)


class Bloqueo(models.Model):
    """Fechas concretas en que la sala no está: mantención, feriado o evento.

    Es distinto de quitar un bloque de la plantilla. Quitarlo lo saca de todas
    las semanas, y un bloqueo vale solo para sus fechas y lleva un motivo que ve
    el solicitante (AC7).

    Sin `bloque` alcanza el día completo, o varios si `hasta` es posterior a
    `desde`. Con `bloque` alcanza solo ese bloque en esa fecha.

    Nunca se borra. Levantarlo deja la fila con quién, cuándo y por qué (AC5 y
    AC6), así que esta tabla es también el registro de mantenciones.
    """

    desde = models.DateField()
    hasta = models.DateField()
    # PROTECT por lo mismo que `activo`: un bloque no se borra, se desactiva.
    bloque = models.ForeignKey(
        Bloque, null=True, blank=True, on_delete=models.PROTECT, related_name="bloqueos"
    )
    motivo = models.CharField(max_length=10, choices=Motivo)
    detalle = models.CharField(max_length=120, blank=True)

    # SET_NULL por lo mismo que en la bitácora de configuración: el registro no
    # puede impedir dar de baja a un administrador, ni desaparecer con él.
    bloqueado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="bloqueos_puestos",
    )
    bloqueado_en = models.DateTimeField(auto_now_add=True)
    levantado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="bloqueos_levantados",
    )
    levantado_en = models.DateTimeField(null=True, blank=True)
    motivo_levantamiento = models.CharField("motivo del levantamiento", max_length=200, blank=True)

    objects = BloqueoQuerySet.as_manager()

    class Meta:
        ordering = ["desde", "bloqueado_en"]
        constraints = [
            models.CheckConstraint(
                condition=Q(hasta__gte=F("desde")),
                name="bloqueo_termina_despues_de_empezar",
            ),
            # Un bloque es de un día de la semana, así que su bloqueo cae en una
            # sola fecha. Para varios días va el día completo.
            models.CheckConstraint(
                condition=Q(bloque__isnull=True) | Q(hasta=F("desde")),
                name="bloqueo_de_bloque_en_una_fecha",
            ),
        ]

    def __str__(self):
        return f"{self.razon}, {self.periodo}, {self.alcance}"

    @property
    def vigente(self):
        return self.levantado_en is None

    @property
    def razon(self):
        """El motivo como lo lee el solicitante (AC7): «Feriado: Fiestas Patrias»."""
        motivo = self.get_motivo_display().capitalize()
        return f"{motivo}: {self.detalle}" if self.detalle else motivo

    @property
    def alcance(self):
        if self.bloque_id is None:
            return "todo el día"
        return f"de {self.bloque.inicio:%H:%M} a {self.bloque.termino:%H:%M}"

    @property
    def periodo(self):
        """Las fechas como las diría una persona, listas para ir en una frase:
        «el martes 14 de octubre», «del 21 al 25 de septiembre»."""
        dia_y_mes = r"j \d\e F"
        if self.desde == self.hasta:
            return "el " + date_format(self.desde, "l " + dia_y_mes)
        hasta = date_format(self.hasta, dia_y_mes)
        if self.desde.month == self.hasta.month:
            return f"del {self.desde.day} al {hasta}"
        return f"del {date_format(self.desde, dia_y_mes)} al {hasta}"

    def cubre(self, fecha, inicio):
        """Si deja fuera el horario que empieza a `inicio` en `fecha`.

        Compara la hora y no el bloque porque una reserva apunta a un horario.
        Si el bloque se quita y se vuelve a crear a la misma hora, el bloqueo
        lo tiene que seguir alcanzando.
        """
        if not self.desde <= fecha <= self.hasta:
            return False
        return self.bloque_id is None or self.bloque.inicio == inicio

    def clean(self):
        """Lo que vale para cualquier bloqueo, venga del panel o de la
        administración de Django. Lo que es solo del panel, como no bloquear el
        pasado, vive en `BloqueoForm`."""
        if self.desde is None or self.hasta is None:
            return  # Falta una fecha: eso lo reporta `clean_fields`, no este.
        if self.hasta < self.desde:
            raise ValidationError(
                {"hasta": "El bloqueo tiene que terminar el mismo día o después."}
            )
        if self.bloque_id is None:
            return
        if self.hasta != self.desde:
            raise ValidationError("Un bloqueo de un solo bloque es de una sola fecha.")
        if self.bloque.dia != self.desde.weekday():
            raise ValidationError({
                "bloque": f"Ese bloque es de los {self.bloque.get_dia_display()} "
                          f"y el {self.desde:%d/%m} no lo es."
            })


def plantilla_semanal():
    """Los bloques activos agrupados por día de la semana. Uno desactivado ya no
    es parte de la jornada."""
    por_dia = defaultdict(list)
    for bloque in Bloque.objects.filter(activo=True):
        por_dia[bloque.dia].append(bloque)
    return por_dia


def bloqueos_por_fecha(desde, hasta):
    """Los bloqueos vigentes de cada fecha del rango, ambos extremos incluidos.

    Devuelve {fecha: [bloqueos]}. Uno de varios días aparece en cada una de sus
    fechas, y una fecha sin bloqueos no aparece.
    """
    por_fecha = defaultdict(list)
    for bloqueo in Bloqueo.objects.vigentes().entre(desde, hasta).select_related("bloque"):
        fecha = max(bloqueo.desde, desde)
        while fecha <= min(bloqueo.hasta, hasta):
            por_fecha[fecha].append(bloqueo)
            fecha += timedelta(days=1)
    return por_fecha


def bloqueo_de(fecha, inicio):
    """El bloqueo vigente que deja fuera ese horario, o None.

    US-17 AC3: es lo que tiene que preguntar quien reciba una solicitud o
    apruebe un ticket. Devuelve el bloqueo y no un sí o un no, porque al
    solicitante hay que decirle por qué (AC7).
    """
    return next(
        (b for b in bloqueos_por_fecha(fecha, fecha).get(fecha, []) if b.cubre(fecha, inicio)),
        None,
    )


def disponibilidad(desde, hasta):
    """Qué bloques se pueden pedir en cada fecha del rango, ambos extremos incluidos.

    La jornada se define por día de la semana y las reservas se piden por fecha.
    Esta función es la traducción entre las dos y el único lugar donde ocurre.
    Los bloques con un bloqueo vigente (US-17) no aparecen. Para saber por qué
    falta uno está `bloqueos_por_fecha`.

    Devuelve {fecha: [bloques]}. Una fecha sin jornada, o bloqueada entera, no
    aparece.
    """
    plantilla = plantilla_semanal()
    bloqueos = bloqueos_por_fecha(desde, hasta)
    dias = {}
    fecha = desde
    while fecha <= hasta:
        del_dia = bloqueos.get(fecha, ())
        bloques = [
            b for b in plantilla.get(fecha.weekday(), ())
            if not any(x.cubre(fecha, b.inicio) for x in del_dia)
        ]
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
