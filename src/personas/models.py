from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone


class Area(models.Model):
    """Área académica, programa o unidad.

    Vive en `personas` y no en `configuracion` porque tiene ciclo de vida y ABM
    propios (US-05), no es un umbral.
    """

    nombre = models.CharField(max_length=120, unique=True)
    prioridad = models.PositiveSmallIntegerField(default=3)
    # US-05 AC3: desactivar la saca del formulario sin borrar su historial.
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Rol(models.TextChoices):
    """Los roles del sistema, que son grupos de Django y no un campo.

    US-08 AC6 permite varios a la vez —hay quien valida y ademas pide la sala—,
    y un campo obligaria a elegir uno. El valor es el nombre del grupo: asi la
    migracion que los crea y el codigo que los pregunta leen lo mismo.
    """

    ADMINISTRADOR = "Administrador", "administrador"
    VALIDADOR = "Validador", "validador"
    APOYO = "Personal de apoyo", "personal de apoyo"
    SOLICITANTE = "Solicitante", "solicitante"


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


class Usuario(AbstractUser):
    """US-01 AC1: se entra con correo, no con nombre de usuario.

    Los roles no son un campo: son grupos de Django, porque US-08 AC6 permite
    varios a la vez y el framework ya lo resuelve.
    """

    username = None
    email = models.EmailField("correo electrónico", unique=True)
    # US-05 AC2: hay docentes que dictan en más de un programa.
    areas = models.ManyToManyField(Area, related_name="usuarios", blank=True)

    # US-01 AC5. El bloqueo es temporal a propósito: si fuera permanente,
    # cualquiera que conozca un correo institucional podría dejar a esa persona
    # fuera del sistema para siempre.
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    def __str__(self):
        return self.email

    def tiene_rol(self, *roles):
        """Si pertenece a alguno de esos grupos. Una consulta, no una por rol."""
        return self.groups.filter(name__in=roles).exists()

    @property
    def esta_bloqueado(self):
        return self.bloqueado_hasta is not None and self.bloqueado_hasta > timezone.now()
