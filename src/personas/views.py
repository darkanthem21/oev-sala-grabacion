from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Usuario

# AC4: el mismo texto para credenciales malas y para correo inexistente. Decir
# "ese correo no existe" le regala al atacante la lista de cuentas.
ERROR_CREDENCIALES = "Correo o contraseña incorrectos."


def destino_tras_login(usuario, request=None):
    """A dónde va alguien recién autenticado.

    US-01 AC3: redirige al formulario / flujo de solicitud de reservas (US-02).
    Si se proporciona `request` y contiene un parámetro `next` válido y seguro
    (que no sea la raíz o el panel marcador), se redirige a esa dirección.
    """
    if request:
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and next_url not in ("/", reverse("panel")):
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return next_url
    return reverse("solicitar")


def _con_error(request, form, mensaje):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    return render(
        request,
        "personas/_formulario_ingreso.html",
        {"form": form, "error": mensaje, "next": next_url},
    )


def _registrar_fallo(usuario):
    """AC5: cinco fallos consecutivos bloquean la cuenta, temporalmente."""
    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= settings.INTENTOS_MAXIMOS:
        usuario.bloqueado_hasta = timezone.now() + timedelta(minutes=settings.MINUTOS_BLOQUEO)
        usuario.intentos_fallidos = 0
    usuario.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])


def entrar(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if request.user.is_authenticated:
        return redirect(destino_tras_login(request.user, request))

    if request.method != "POST":
        return render(
            request,
            "personas/login.html",
            {"form": AuthenticationForm(), "next": next_url},
        )

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
        destino = destino_tras_login(entrante, request)
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204, headers={"HX-Redirect": destino})
        return redirect(destino)

    if usuario:
        _registrar_fallo(usuario)
    return _con_error(request, form, ERROR_CREDENCIALES)


@login_required
def panel(request):
    """Marcador de posición del panel de reservas (US-02). Redirige a solicitar."""
    return redirect("solicitar")
