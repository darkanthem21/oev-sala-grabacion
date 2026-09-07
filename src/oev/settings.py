import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Nada de esto vive en el codigo: lo pone el servidor de turno por entorno.
# Mudarse de alojamiento es cambiar variables, no editar archivos.
SECRET_KEY = os.environ.get("SECRET_KEY", "clave-solo-para-desarrollo")
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_ORIGINS", "").split(",") if o]

# Detras de un proxy (Caddy): el host y el esquema reales llegan en cabeceras.
# Sin la segunda linea Django cree que la peticion es http aunque el navegador
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
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "oev.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Lo compartido por todos los modulos; lo propio va en <modulo>/templates/.
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
# Estaticos compartidos por todos los modulos; los propios van en <modulo>/static/.
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "personas.Usuario"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"

# US-01 AC5. Por entorno hasta que exista el modulo `configuracion`: el RNF 1
# exige que el cliente pueda cambiar estos umbrales sin tocar el codigo.
INTENTOS_MAXIMOS = int(os.environ.get("INTENTOS_MAXIMOS", "5"))
MINUTOS_BLOQUEO = int(os.environ.get("MINUTOS_BLOQUEO", "15"))

# US-01 AC6. Sin relay institucional todavia (es una de las preguntas abiertas
# del despliegue), asi que por defecto el correo se imprime en consola y no se
# pierde en silencio. En el servidor se cambia por variable de entorno.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-responder@uach.cl")
