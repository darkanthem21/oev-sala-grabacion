import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Nada de esto vive en el código; lo pone por entorno el servidor de turno.
# Mudarse de alojamiento es cambiar variables, no editar archivos.
SECRET_KEY = os.environ.get("SECRET_KEY", "clave-solo-para-desarrollo")
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_ORIGINS", "").split(",") if o]

# Detrás de un proxy (Caddy) el host y el esquema reales llegan en cabeceras.
# Sin la segunda línea Django cree que la petición es http aunque el navegador
# la haya hecho por https, y rechaza el POST del login por CSRF.
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
]

MIDDLEWARE = [
    # El de seguridad va primero y el de clickjacking último, por el orden en que
    # miran la petición y la respuesta. Con solo agregarlos ya salen nosniff,
    # Referrer-Policy y COOP, que son los valores por defecto de Django. No hay
    # SSL_REDIRECT ni HSTS porque el TLS lo hace Caddy y el dominio del curso lo
    # comparten todos los grupos.
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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
# Estáticos compartidos por todos los módulos; los propios van en <modulo>/static/.
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "personas.Usuario"
LOGIN_URL = "login_solicitante"
LOGIN_REDIRECT_URL = "/"

# US-01 AC6. Todavía no hay relay institucional, así que por defecto el correo
# se imprime en consola y no se pierde en silencio. En el servidor se cambia por
# variable de entorno.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-responder@uach.cl")

