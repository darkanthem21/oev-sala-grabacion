import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Nada de esto vive en el código; lo pone por entorno el servidor de turno.
# Mudarse de alojamiento es cambiar variables, no editar archivos.
# La clave por defecto solo sirve en desarrollo y en las pruebas: al arrancar en
# producción, `check --deploy` la rechaza por débil y el contenedor no levanta.
SECRET_KEY = os.environ.get("SECRET_KEY", "clave-solo-para-desarrollo")
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_ORIGINS", "").split(",") if o]

# Detrás de un proxy (Caddy) el host y el esquema reales llegan en cabeceras.
# Sin la segunda línea Django cree que la petición es http aunque el navegador
# la haya hecho por https, y rechaza el POST del login por CSRF.
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Fuera de desarrollo la sesión y el token CSRF viajan solo por https. Los
# navegadores aceptan cookies seguras en http://localhost, así que la simulación
# local sigue funcionando.
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
# La redirección a https y el HSTS los pone el proxy que termina el TLS, no
# Django: así no se fijan para un dominio que comparten otros sistemas.
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "personas",
    "agenda",
    "configuracion",
    "solicitudes",
    "uso",
    "notificaciones",
]

MIDDLEWARE = [
    # El de seguridad va primero y el de clickjacking último, por el orden en que
    # miran la petición y la respuesta. Con solo agregarlos ya salen nosniff,
    # Referrer-Policy y COOP, que son los valores por defecto de Django. No hay
    # SSL_REDIRECT ni HSTS porque el TLS lo hace el proxy.
    "django.middleware.security.SecurityMiddleware",
    # gunicorn no sirve estáticos; whitenoise sí, y la imagen no depende de que
    # el proxy de cada servidor los sepa servir.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Con DEBUG=0 Django no escribe los errores en la consola: los manda por correo
# a ADMINS, que está vacío. Sin esto un 500 no deja traza en `docker logs`.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"sin_debug": {"()": "django.utils.log.RequireDebugFalse"}},
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "level": "WARNING", "filters": ["sin_debug"]},
    },
    "root": {"handlers": ["consola"]},
}

ROOT_URLCONF = "oev.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Lo compartido por todos los módulos; lo propio va en <modulo>/templates/.
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DB_ENGINE = os.environ.get("DB_ENGINE", "postgresql")
if DB_ENGINE == "sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "oev"),
            "USER": os.environ.get("POSTGRES_USER", "oev"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "oev"),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": "5432",
        }
    }


LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# La imagen corre collectstatic y fija ESTATICOS_COMPRIMIDOS=1: nombres con hash
# (caché larga) y versiones comprimidas. En desarrollo y en las pruebas no hay
# collectstatic, así que se sirven tal cual desde cada módulo.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if os.environ.get("ESTATICOS_COMPRIMIDOS") == "1"
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media")))
# Estáticos compartidos por todos los módulos; los propios van en <modulo>/static/.
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "personas.Usuario"
LOGIN_URL = "login_solicitante"
LOGIN_REDIRECT_URL = "/"

# US-01 AC6. Todavía no hay relay institucional, así que por defecto el correo
# se imprime en consola y no se pierde en silencio. En el servidor se cambia por
# variable de entorno; puerto y TLS por defecto son los de cualquier proveedor
# actual (587 con STARTTLS).
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-responder@uach.cl")

# US-03: el recordatorio lo manda la tarea, sin una petición de donde sacar el
# dominio para sus enlaces. En el servidor, https://oev.inf.uach.cl.
URL_BASE = os.environ.get("URL_BASE", "http://localhost:8000").rstrip("/")

