from datetime import timedelta

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from configuracion.models import Parametros

from .models import Usuario

# AC4: el mismo texto para credenciales malas y para correo inexistente. Decir
# "ese correo no existe" le regala al atacante la lista de cuentas.
ERROR_CREDENCIALES = "Correo o contraseña incorrectos."


def destino_tras_login(usuario):
    """A dónde va alguien recién autenticado.

    US-01 AC3 dice "panel principal de reservas", que es US-02 y todavía no
    existe. Cuando exista, se cambia esta función y nada más.

    Las puertas son dos desde el 08/09: `login` para solicitantes y
    `login_gestion` para la administración. Ambas reusan `entrar`, así que la
    autenticación, el bloqueo por intentos y la recuperación de clave viven en un
    solo lugar; lo que cambia es la plantilla y a quién se deja pasar.

    US-04: el administrador entra directo a su panel. El rol todavía no es un
    grupo —eso es US-08—, así que decide el mismo permiso que abre /admin.
    """
    if usuario.is_staff:
        return reverse("panel_bloques")
    return reverse("panel")


def _con_error(request, form, mensaje, ruta):
    return render(
        request,
        "personas/_formulario_ingreso.html",
        {"form": form, "error": mensaje, "ruta": ruta},
    )


def _registrar_fallo(usuario):
    """AC5: unos cuantos fallos seguidos bloquean la cuenta, temporalmente.

    Cuantos y por cuanto los fija el administrador desde el panel (US-04).
    """
    parametros = Parametros.cargar()
    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= parametros.intentos_maximos:
        usuario.bloqueado_hasta = timezone.now() + timedelta(minutes=parametros.minutos_bloqueo)
        usuario.intentos_fallidos = 0
    usuario.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])


def entrar(request, plantilla="personas/login.html", ruta="login", solo_staff=False):
    """Las dos puertas del sistema. La de gestion cambia la plantilla y a quien
    deja pasar; la autenticacion, el bloqueo y la recuperacion de clave son las
    mismas para ambas."""
    if request.method != "POST":
        return render(request, plantilla, {"form": AuthenticationForm(), "ruta": ruta})

    form = AuthenticationForm(request, data=request.POST)
    usuario = Usuario.objects.filter(email__iexact=request.POST.get("username", "")).first()

    if usuario and usuario.esta_bloqueado:
        minutos = max(1, int((usuario.bloqueado_hasta - timezone.now()).total_seconds() // 60) + 1)
        return _con_error(
            request, form, f"Cuenta bloqueada. Vuelve a intentar en {minutos} minutos.", ruta
        )

    if form.is_valid():
        entrante = form.get_user()
        # La puerta de gestion no responde "no eres administrador": ese mensaje la
        # convierte en un oraculo para saber que correos existen y cuales mandan.
        # Mismo texto que una clave mala, y sin sesion.
        if solo_staff and not entrante.is_staff:
            return _con_error(request, form, ERROR_CREDENCIALES, ruta)
        if entrante.intentos_fallidos or entrante.bloqueado_hasta:
            entrante.intentos_fallidos = 0
            entrante.bloqueado_hasta = None
            entrante.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
        login(request, entrante)
        # 204 sin cuerpo: no hay nada que pegar, el navegador navega de verdad.
        return HttpResponse(status=204, headers={"HX-Redirect": destino_tras_login(entrante)})

    if usuario:
        _registrar_fallo(usuario)
    return _con_error(request, form, ERROR_CREDENCIALES, ruta)


@login_required
def panel(request):
    """Marcador de posición del panel de reservas (US-02)."""
    return render(request, "personas/panel.html")
