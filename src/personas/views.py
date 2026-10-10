from datetime import timedelta

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from configuracion.models import Parametros

from .models import Rol, Usuario



def destino_tras_login(usuario):
    """A qué panel lleva la raíz `/` a alguien ya autenticado. Tras entrar
    manda la puerta (`destino`), no esto.

    US-01 AC3 dice "panel principal de reservas": para el solicitante es el
    formulario de US-02.

    Los roles ya son grupos de Django (US-08 AC6), así que alguien puede tener
    varios: el orden de abajo es la prioridad, no una clasificación. `is_staff`
    sigue contando como administrador porque el superusuario que crea el
    despliegue no pertenece a ningún grupo.
    """
    if usuario.is_staff or usuario.tiene_rol(Rol.ADMINISTRADOR):
        return reverse("panel_bloques")
    if usuario.tiene_rol(Rol.VALIDADOR):
        return reverse("panel_validador")
    if usuario.tiene_rol(Rol.APOYO):
        return reverse("panel_apoyo")
    return reverse("solicitar")


def _con_error(request, form, ruta):
    """AC4: el mismo texto para clave mala, correo inexistente, cuenta sin el rol
    de la puerta y cuenta bloqueada. Cualquier diferencia le regalaría al atacante
    la lista de cuentas. La regla del bloqueo (AC5) va en el texto para que quien
    quedó bloqueado entienda por qué no entra."""
    parametros = Parametros.cargar()
    mensaje = (
        f"Correo o contraseña incorrectos. Tras {parametros.intentos_maximos} intentos "
        f"seguidos la cuenta se bloquea {parametros.minutos_bloqueo} minutos."
    )
    return render(
        request,
        "personas/_formulario_ingreso.html",
        {"form": form, "error": mensaje, "ruta": ruta, "next": request.POST.get("next", "")},
    )


def _registrar_fallo(usuario):
    """AC5: unos cuantos fallos seguidos bloquean la cuenta, temporalmente.

    Cuántos y por cuánto los fija el administrador desde el panel (US-04).
    """
    parametros = Parametros.cargar()
    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= parametros.intentos_maximos:
        usuario.bloqueado_hasta = timezone.now() + timedelta(minutes=parametros.minutos_bloqueo)
        usuario.intentos_fallidos = 0
    usuario.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])


def _puede_pasar(usuario, rol):
    """Quién cruza esta puerta.

    En la de administración vale también `is_staff`, porque el superusuario del
    despliegue no pertenece a ningún grupo y quedaría afuera de su propia puerta.
    """
    if rol == Rol.ADMINISTRADOR and usuario.is_staff:
        return True
    return usuario.tiene_rol(rol)


def entrar(request, rol, destino, ruta, titulo, puerta, nombre):
    """Las puertas del sistema. Cada una cambia el título, a quién deja pasar, a
    qué panel lo lleva (`destino`, nombre de URL) y su panel de color (`puerta`
    y `nombre`). La plantilla, la autenticación, el bloqueo por intentos y la
    recuperación de clave son las mismas para todas."""
    contexto = {"form": AuthenticationForm(), "ruta": ruta, "titulo": titulo, "next": request.GET.get("next", ""),
                "puerta": puerta, "nombre": nombre}
    if request.method != "POST":
        return render(request, "personas/login.html", contexto)

    form = AuthenticationForm(request, data=request.POST)
    usuario = Usuario.objects.filter(email__iexact=request.POST.get("username", "")).first()
    # Se revisa la clave aunque la cuenta esté bloqueada: si no, la respuesta
    # rápida (sin calcular el hash) delataría qué cuentas existen.
    valido = form.is_valid()

    if usuario and usuario.esta_bloqueado:
        return _con_error(request, form, ruta)

    if valido:
        entrante = form.get_user()
        # Una puerta de rol no responde "no eres administrador". Ese mensaje la
        # convertiría en un oráculo para saber qué correos existen y cuáles
        # mandan, así que contesta lo mismo que una clave mala, y sin sesión.
        if not _puede_pasar(entrante, rol):
            return _con_error(request, form, ruta)
        if entrante.intentos_fallidos or entrante.bloqueado_hasta:
            entrante.intentos_fallidos = 0
            entrante.bloqueado_hasta = None
            entrante.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
        login(request, entrante)
        # Vuelve a la página que pidió el ingreso (p. ej. el enlace de
        # confirmación del correo), solo si es de este sitio.
        siguiente = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(siguiente, {request.get_host()}, request.is_secure()):
            siguiente = reverse(destino)
        # 204 sin cuerpo porque no hay nada que pegar; el navegador navega.
        return HttpResponse(status=204, headers={"HX-Redirect": siguiente})

    if usuario:
        _registrar_fallo(usuario)
    return _con_error(request, form, ruta)


@login_required
def panel(request):
    """La raíz lleva a cada uno a su panel, por la prioridad de sus roles."""
    return redirect(destino_tras_login(request.user))
