from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, UserManager
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.utils.formats import date_format


class Area(models.Model):
    """Área académica, programa o unidad.

    Vive en `personas` porque tiene ciclo de vida y ABM propios (US-05). No es
    un umbral.
    """

    nombre = models.CharField(max_length=120, unique=True)
    prioridad = models.PositiveSmallIntegerField(default=3)
    # US-05 AC3: desactivar la saca del formulario sin borrar su historial.
    activa = models.BooleanField(default=True)
    # US-05 AC4: lo que el validador tiene que tener en cuenta, como que
    # Educación Continua no graba en horario laboral (06/08, 03:48).
    nota = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class CambioArea(models.Model):
    """US-05 AC6: quién cambió qué de un área, de cuánto a cuánto y cuándo.

    Igual que `CambioParametro`. La creación queda como el paso de vacío al
    nombre y la nota.
    """

    # PROTECT porque las áreas no se borran (AC3): si alguien lo intenta desde
    # el shell, el registro lo frena en vez de desaparecer con ella.
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="cambios")
    campo = models.CharField(max_length=50)
    antes = models.TextField()
    despues = models.TextField()
    quien = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cambios_de_areas",
    )
    cuando = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cuando", "-id"]
        verbose_name = "cambio de área"
        verbose_name_plural = "cambios de áreas"

    def __str__(self):
        return f"{self.area}: {self.etiqueta} {self.antes} → {self.despues}"

    @property
    def etiqueta(self):
        try:
            return Area._meta.get_field(self.campo).verbose_name
        except FieldDoesNotExist:
            # Un campo que se quitó del modelo sigue en el registro.
            return self.campo


class Rol(models.TextChoices):
    """Los roles del sistema, guardados como grupos de Django.

    US-08 AC6 permite tener varios a la vez (hay quien valida y además pide la
    sala) y un campo obligaría a elegir uno. El valor es el nombre del grupo,
    así la migración que los crea y el código que los pregunta leen lo mismo.
    """

    ADMINISTRADOR = "Administrador", "administrador"
    VALIDADOR = "Validador", "validador"
    APOYO = "Personal de apoyo", "personal de apoyo"
    SOLICITANTE = "Solicitante", "solicitante"


# La puerta de cada rol (`<puerta>/entrar/`, `login_<puerta>`), que también
# elige su ícono y su color (AC7).
PUERTA_DEL_ROL = {
    Rol.ADMINISTRADOR: "gestion",
    Rol.VALIDADOR: "validacion",
    Rol.APOYO: "apoyo",
    Rol.SOLICITANTE: "solicitante",
}

ULTIMO_ADMINISTRADOR = "Tiene que quedar al menos un administrador activo."


class UsuarioManager(UserManager):
    """El de Django exige `username`; acá la identidad es el correo."""

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("El correo es obligatorio")
        usuario = self.model(email=self.normalize_email(email), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)

    def get_by_natural_key(self, email):
        # US-01: el correo no distingue mayúsculas, igual que la búsqueda con que
        # la vista cuenta los intentos. Antes «Ana@uach.cl» con su clave correcta
        # sumaba fallos hasta quedar bloqueada.
        return self.get(email__iexact=email)


class Usuario(AbstractUser):
    """US-01 AC1: se entra con correo, no con nombre de usuario.

    Los roles viven en grupos de Django (ver `Rol`), porque US-08 AC6 permite
    tener varios a la vez y el framework ya lo resuelve.
    """

    username = None
    email = models.EmailField("correo electrónico", unique=True)
    # US-05 AC2: hay docentes que dictan en más de un programa.
    areas = models.ManyToManyField(Area, related_name="usuarios", blank=True, verbose_name="áreas")

    # US-01 AC5. El bloqueo es temporal porque uno permanente dejaría que
    # cualquiera que conozca un correo institucional saque a esa persona del
    # sistema para siempre.
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # En minúsculas, así dos cuentas no pueden diferir solo en mayúsculas y
        # `get_by_natural_key` nunca encuentra dos.
        self.email = self.email.lower()
        with transaction.atomic():
            if self.pk and not self.is_active:
                impedir_quedar_sin_administrador({self.pk})
            super().save(*args, **kwargs)

    def tiene_rol(self, *roles):
        """Si pertenece a alguno de esos grupos, en una sola consulta."""
        return self.groups.filter(name__in=roles).exists()

    @property
    def es_administrador(self):
        """Quién abre el panel. `is_staff` cuenta mientras la cuenta técnica no
        tenga el rol (AC11)."""
        return self.is_active and (self.is_staff or self.tiene_rol(Rol.ADMINISTRADOR))

    @property
    def esta_bloqueado(self):
        return self.bloqueado_hasta is not None and self.bloqueado_hasta > timezone.now()

    @property
    def sancion_vigente(self):
        """US-10: la sanción que hoy le impide pedir, o None.

        Si se pisan dos, la que termina más tarde, porque es la que dice desde
        cuándo puede volver a pedir. No se guarda en caché: una sanción
        levantada a media sesión tiene que dejar de contar en la próxima página.
        """
        return Sancion.objects.filter(usuario=self).vigentes().order_by("-termino").first()


def impedir_quedar_sin_administrador(salen):
    """US-08 AC6: falla si las cuentas `salen` son todos los administradores activos.
    El bloqueo hace que dos bajas a la vez se esperen y la segunda vea la primera."""
    activos = set(
        Usuario.objects.select_for_update()
        .filter(is_active=True, groups__name=Rol.ADMINISTRADOR)
        .values_list("pk", flat=True)
    )
    if activos and activos <= set(salen):
        raise ValidationError(ULTIMO_ADMINISTRADOR)


@receiver(m2m_changed, sender=Usuario.groups.through)
def _sin_quitar_el_ultimo_administrador(instance, action, reverse, pk_set, **kwargs):
    """La misma regla para el rol, venga de la pestaña, del panel de Django o del
    shell, en cualquiera de los dos sentidos de la relación."""
    if action not in ("pre_remove", "pre_clear"):
        return
    if reverse:
        if instance.name == Rol.ADMINISTRADOR:
            salen = pk_set if action == "pre_remove" else instance.user_set.values_list("pk", flat=True)
            impedir_quedar_sin_administrador(salen)
    elif action == "pre_clear" or Group.objects.filter(pk__in=pk_set, name=Rol.ADMINISTRADOR).exists():
        impedir_quedar_sin_administrador({instance.pk})


class CambioUsuario(models.Model):
    """US-08 AC10: quién cambió qué de una cuenta y cuándo, como `CambioArea`.
    Roles y áreas se guardan como la lista entera, antes y después."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cambios")
    campo = models.CharField(max_length=50)
    antes = models.TextField(blank=True)
    despues = models.TextField(blank=True)
    quien = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cambios_de_cuentas",
    )
    cuando = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cuando", "-id"]
        verbose_name = "cambio de cuenta"
        verbose_name_plural = "cambios de cuentas"

    def __str__(self):
        return f"{self.usuario}: {self.etiqueta} {self.antes} → {self.despues}"

    @property
    def etiqueta(self):
        if self.campo == "roles":
            return "roles"
        try:
            return Usuario._meta.get_field(self.campo).verbose_name
        except FieldDoesNotExist:
            return self.campo


class SancionQuerySet(models.QuerySet):
    """Vigente y pasada se calculan contra la fecha de hoy en Santiago, así la
    rehabilitación es automática y no hace falta una tarea que la apague."""

    def vigentes(self, hoy=None):
        """Las que rigen hoy: empezaron, no terminaron y nadie las levantó. El día
        de término cuenta entero."""
        hoy = hoy or timezone.localdate()
        return self.filter(inicio__lte=hoy, termino__gte=hoy, levantada_en__isnull=True)

    def pasadas(self, hoy=None):
        """Las que terminaron o se levantaron antes. La más reciente primero."""
        hoy = hoy or timezone.localdate()
        return self.filter(Q(termino__lt=hoy) | Q(levantada_en__isnull=False)).order_by("-termino", "-id")


class Sancion(models.Model):
    """Una suspensión temporal del derecho a pedir la sala (US-10).

    Vive en `personas` porque es un dato de la persona (README.md). Solo impide
    pedir: las reservas que ya estaban aprobadas y las solicitudes en revisión
    siguen su curso (AC6, decidido el 20/10).

    Las fechas son días completos en la hora de Santiago: rige desde el primer
    minuto de `inicio` hasta las 23:59 de `termino`. Nunca se borra; levantarla
    antes de tiempo deja quién, cuándo y por qué, como un bloqueo de la sala.
    """

    # PROTECT como `Solicitud.solicitante`: el historial de una persona no puede
    # desaparecer con su cuenta.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sanciones",
        verbose_name="persona sancionada",
    )
    motivo = models.CharField(max_length=300)
    inicio = models.DateField(default=timezone.localdate)
    termino = models.DateField("término")

    # SET_NULL por lo mismo que en los bloqueos: el registro no puede impedir dar
    # de baja a un administrador, ni desaparecer con él.
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="sanciones_puestas",
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    levantada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="sanciones_levantadas",
    )
    levantada_en = models.DateTimeField(null=True, blank=True)
    motivo_levantamiento = models.CharField("motivo del levantamiento", max_length=200, blank=True)

    objects = SancionQuerySet.as_manager()

    class Meta:
        verbose_name = "sanción"
        verbose_name_plural = "sanciones"
        ordering = ["-inicio", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(termino__gte=F("inicio")),
                name="sancion_termina_despues_de_empezar",
            ),
        ]

    def __str__(self):
        return f"{self.usuario}, {self.periodo}"

    @property
    def levantada(self):
        return self.levantada_en is not None

    @property
    def periodo(self):
        """Las fechas como las diría una persona: «del 3 al 30 de noviembre»."""
        dia_y_mes = r"j \d\e F"
        if self.inicio == self.termino:
            return "el " + date_format(self.inicio, "l " + dia_y_mes)
        termino = date_format(self.termino, dia_y_mes)
        if self.inicio.month == self.termino.month:
            return f"del {self.inicio.day} al {termino}"
        return f"del {date_format(self.inicio, dia_y_mes)} al {termino}"

    @property
    def hasta(self):
        """Hasta cuándo rige, con la hora: el día de término cuenta entero."""
        return date_format(self.termino, r"l j \d\e F \d\e Y") + " a las 23:59"

    @property
    def rehabilita(self):
        """Desde qué día se puede volver a pedir."""
        return date_format(self.termino + timedelta(days=1), r"l j \d\e F \d\e Y")

    def clean(self):
        """Una sanción sin término no se permite (lo exige la columna) y una que
        empieza en el futuro tampoco: se pone cuando corresponde, no por
        adelantado (decidido el 20/10)."""
        if self.inicio is None or self.termino is None:
            return  # Falta una fecha: eso lo reporta `clean_fields`, no este.
        if self.inicio > timezone.localdate():
            raise ValidationError({"inicio": "Una sanción no puede empezar en una fecha futura."})
        if self.termino < self.inicio:
            raise ValidationError({"termino": "La sanción tiene que terminar el mismo día que empieza o después."})
