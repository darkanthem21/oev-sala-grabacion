from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .models import Usuario

# AC4: el mismo texto para credenciales malas y para correo inexistente. Decir
# "ese correo no existe" le regala al atacante la lista de cuentas.
ERROR_CREDENCIALES = "Correo o contraseña incorrectos."


def destino_tras_login(usuario):
    """A dónde va alguien recién autenticado.

    US-01 AC3 dice "panel principal de reservas", que es US-02 y todavía no
    existe. Cuando exista, se cambia esta función y nada más.

    Es también el punto donde se decide el destino por rol, si se confirma que
    los distintos tipos de usuario entran por la misma puerta. Si se decide que
    entran por puertas distintas, se agrega otra URL que reusa `entrar`: la
    autenticación no se duplica.

    US-04: el administrador entra directo a su panel. El rol todavía no es un
    grupo —eso es US-08—, así que decide el mismo permiso que abre /admin.
    """
    if usuario.is_staff:
        return reverse("panel_bloques")
    return reverse("panel")


def _con_error(request, form, mensaje):
    return render(request, "personas/_formulario_ingreso.html", {"form": form, "error": mensaje})


def _registrar_fallo(usuario):
    """AC5: cinco fallos consecutivos bloquean la cuenta, temporalmente."""
    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= settings.INTENTOS_MAXIMOS:
        usuario.bloqueado_hasta = timezone.now() + timedelta(minutes=settings.MINUTOS_BLOQUEO)
        usuario.intentos_fallidos = 0
    usuario.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])


def entrar(request):
    if request.method != "POST":
        return render(request, "personas/login.html", {"form": AuthenticationForm()})

    form = AuthenticationForm(request, data=request.POST)
    usuario = Usuario.objects.filter(email__iexact=request.POST.get("username", "")).first()

    if usuario and usuario.esta_bloqueado:
        minutos = max(1, int((usuario.bloqueado_hasta - timezone.now()).total_seconds() // 60) + 1)
        return _con_error(request, form, f"Cuenta bloqueada. Vuelve a intentar en {minutos} minutos.")

    if form.is_valid():
        entrante = form.get_user()
        if entrante.intentos_fallidos or entrante.bloqueado_hasta:
            entrante.intentos_fallidos = 0
            entrante.bloqueado_hasta = None
            entrante.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
        login(request, entrante)
        # 204 sin cuerpo: no hay nada que pegar, el navegador navega de verdad.
        return HttpResponse(status=204, headers={"HX-Redirect": destino_tras_login(entrante)})

    if usuario:
        _registrar_fallo(usuario)
    return _con_error(request, form, ERROR_CREDENCIALES)


@login_required
def panel(request):
    """Marcador de posición del panel de reservas (US-02)."""
    return render(request, "personas/panel.html")
