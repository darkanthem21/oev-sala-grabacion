from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone


class Area(models.Model):
    """Área académica, programa o unidad.

    Vive en `personas` porque tiene ciclo de vida y ABM propios (US-05). No es
    un umbral.
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
    """Los roles del sistema, guardados como grupos de Django.

    US-08 AC6 permite tener varios a la vez (hay quien valida y además pide la
    sala) y un campo obligaría a elegir uno. El valor es el nombre del grupo,
    así la migración que los crea y el código que los pregunta leen lo mismo.
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
    areas = models.ManyToManyField(Area, related_name="usuarios", blank=True)

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
        super().save(*args, **kwargs)

    def tiene_rol(self, *roles):
        """Si pertenece a alguno de esos grupos, en una sola consulta."""
        return self.groups.filter(name__in=roles).exists()

    @property
    def esta_bloqueado(self):
        return self.bloqueado_hasta is not None and self.bloqueado_hasta > timezone.now()
