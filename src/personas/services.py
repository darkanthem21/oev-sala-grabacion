"""US-10 y US-12: aplicar y levantar sanciones.
US-05: guardar y desactivar áreas, con su registro de cambios.
US-08: crear, editar y desactivar cuentas, con su registro de cambios."""
import logging
import secrets
from datetime import timedelta
from functools import partial

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from configuracion.models import Parametros
from notificaciones.services import avisar

from .models import PUERTA_DEL_ROL, Area, CambioArea, CambioUsuario, Rol, Sancion, Usuario

logger = logging.getLogger(__name__)

# Lo que el registro sigue de una cuenta (AC10). Los permisos de Django van
# porque hoy abren el panel igual que el rol.
CAMPOS_DE_CUENTA = ["email", "first_name", "last_name", "is_active", "is_staff", "is_superuser"]
CUENTA_NUEVA = {
    "email": "", "first_name": "", "last_name": "", "is_active": "Sí", "is_staff": "No", "is_superuser": "No",
    "roles": "", "areas": "",
}


def _legible(valor):
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    return "" if valor is None else str(valor)


def cambios_de_area(form):
    """Lo que el formulario cambia, campo por campo, antes de guardarlo.
    `changed_data` deja fuera lo que no cambió, así que guardar sin tocar nada
    no ensucia el registro."""
    return [(campo, _legible(form.initial.get(campo)), _legible(form.cleaned_data[campo])) for campo in form.changed_data]


def registrar_cambios(area, cambios, quien):
    CambioArea.objects.bulk_create(
        CambioArea(area=area, campo=campo, antes=antes, despues=despues, quien=quien)
        for campo, antes, despues in cambios
    )


@transaction.atomic
def guardar_area(form, quien):
    """Crea o edita un área y anota lo que cambió (US-05 AC6). Atómico, como
    `configuracion.services.guardar`: un cambio sin registro es lo que el
    criterio pide evitar."""
    cambios = cambios_de_area(form)
    area = form.save()
    registrar_cambios(area, cambios, quien)
    return area


@transaction.atomic
def cambiar_estado(area, activa, quien):
    """Desactiva o reactiva un área (AC3) y lo anota. Es un UPDATE condicionado
    al estado contrario, así dos clics seguidos o dos administradores a la vez
    dejan un solo registro. Devuelve si cambió algo."""
    if not Area.objects.filter(pk=area.pk, activa=not activa).update(activa=activa):
        return False
    CambioArea.objects.create(
        area=area, campo="activa", antes="No" if activa else "Sí", despues="Sí" if activa else "No", quien=quien,
    )
    return True


def foto_de_cuenta(pk):
    """La cuenta como está en la base. Se lee de nuevo porque un formulario válido
    ya le cambió los atributos a su instancia."""
    if pk is None:
        return CUENTA_NUEVA
    usuario = Usuario.objects.get(pk=pk)
    foto = {campo: _legible(getattr(usuario, campo)) for campo in CAMPOS_DE_CUENTA}
    foto["roles"] = ", ".join(sorted(usuario.groups.values_list("name", flat=True)))
    foto["areas"] = ", ".join(sorted(usuario.areas.values_list("nombre", flat=True)))
    return foto


def registrar_cambios_de_cuenta(usuario, antes, quien):
    despues = foto_de_cuenta(usuario.pk)
    CambioUsuario.objects.bulk_create(
        CambioUsuario(usuario=usuario, campo=campo, antes=antes[campo], despues=despues[campo], quien=quien)
        for campo in despues if antes[campo] != despues[campo]
    )


def puede_cambiar_cuenta(cuenta, quien):
    """Las cuentas de administrador las cambia solo el superusuario, la de soporte
    de la OEV (pedido de la profesora). Uno mismo sí edita sus datos. Las técnicas
    (`is_staff`, el superusuario) cuentan como de administrador aunque no tengan
    el rol: si no, otro administrador podría cambiarles el correo y quedarse con
    ellas pidiendo una contraseña nueva."""
    return (
        quien.is_superuser or cuenta.pk is None or cuenta.pk == quien.pk
        or not (cuenta.is_staff or cuenta.is_superuser or cuenta.tiene_rol(Rol.ADMINISTRADOR))
    )


def _exigir_que_pueda(cuenta, quien):
    if not puede_cambiar_cuenta(cuenta, quien):
        raise ValidationError("Solo el superusuario cambia la cuenta de otro administrador.")


@transaction.atomic
def guardar_usuario(form, quien):
    """Crea o edita una cuenta con sus roles y áreas (AC2) y anota lo que cambió
    (AC10). La regla del último administrador la pone el modelo."""
    usuario = form.instance
    roles = form.cleaned_data["roles"]
    _exigir_que_pueda(usuario, quien)
    ya_es_admin = usuario.pk is not None and usuario.tiene_rol(Rol.ADMINISTRADOR)
    if Rol.ADMINISTRADOR in roles and not ya_es_admin and not quien.is_superuser:
        raise ValidationError("Solo el superusuario da el rol de administrador.")
    if usuario.pk == quien.pk and ya_es_admin and Rol.ADMINISTRADOR not in roles:
        raise ValidationError("No puedes quitarte a ti mismo el rol de administrador.")
    solicitante = Rol.SOLICITANTE in roles
    if solicitante and not any(area.activa for area in form.cleaned_data["areas"]):
        raise ValidationError({"areas": "Un solicitante necesita al menos un área activa para pedir la sala."})
    antes = foto_de_cuenta(usuario.pk)
    if usuario.pk is None:
        # AC3: nadie la conoce. Va una al azar porque Django no manda el enlace
        # de /clave/ a una cuenta sin contraseña usable.
        usuario.set_password(secrets.token_urlsafe(32))
    try:
        with transaction.atomic():
            usuario = form.save()
    except IntegrityError:
        # Doble clic: los dos envíos pasaron `clean_email` antes de que el primero guardara.
        raise ValidationError({"email": "Ya hay una cuenta con ese correo."})
    usuario.groups.set(Group.objects.filter(name__in=roles))
    if not solicitante:
        # El área es de quien pide la sala; validadores y apoyo son ayudantes sin área.
        usuario.areas.clear()
    registrar_cambios_de_cuenta(usuario, antes, quien)
    return usuario


@transaction.atomic
def cambiar_estado_de_cuenta(usuario, activa, quien):
    """Desactiva o reactiva una cuenta (AC4); nunca se borra, porque su historial
    sostiene sanciones y reportes. Devuelve si cambió algo."""
    if not activa and usuario.pk == quien.pk:
        raise ValidationError("No puedes desactivar tu propia cuenta.")
    _exigir_que_pueda(usuario, quien)
    usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
    if usuario.is_active == activa:
        return False
    antes = foto_de_cuenta(usuario.pk)
    usuario.is_active = activa
    usuario.save(update_fields=["is_active"])
    registrar_cambios_de_cuenta(usuario, antes, quien)
    return True


def enviar_acceso(usuario):
    """AC3: el correo con el enlace de /clave/ para fijar la contraseña y la
    puerta de cada rol. Devuelve si salió."""
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    enlace = reverse("password_reset_confirm", args=[uid, default_token_generator.make_token(usuario)])
    roles = set(usuario.groups.values_list("name", flat=True))
    puertas = [
        (rol.label, settings.URL_BASE + reverse(f"login_{PUERTA_DEL_ROL[rol]}")) for rol in Rol if rol in roles
    ]
    try:
        avisar(usuario.email, "Tu cuenta en la sala de grabación de la OEV", "notificaciones/bienvenida.txt", {
            "nombre": usuario.first_name or usuario.email,
            "correo": usuario.email,
            "enlace": settings.URL_BASE + enlace,
            "dias": settings.PASSWORD_RESET_TIMEOUT // 86400,
            "puertas": puertas,
        })
    except Exception:
        logger.exception("No salió el correo para fijar la contraseña de %s.", usuario.email)
        return False
    return True


def levantar(sancion, quien, motivo):
    """Termina la sanción antes de tiempo y anota quién, cuándo y por qué.

    Es un UPDATE condicionado a que siga vigente, así dos administradores
    levantando la misma a la vez no pisan el registro del primero. Las reservas
    no cambian: la sanción nunca las tocó (AC6).
    """
    levantadas = Sancion.objects.filter(pk=sancion.pk).vigentes().update(
        levantada_por=quien, levantada_en=timezone.now(), motivo_levantamiento=motivo
    )
    if not levantadas:
        raise ValidationError("Esa sanción ya no está vigente: terminó o alguien la levantó.")
    sancion.refresh_from_db()
    return sancion


def termino_por_defecto(inicio, dias=None):
    """US-12: el último día de una sanción de `dias_sancion` días que empieza en
    `inicio`. El día de término cuenta entero (rige hasta las 23:59), así que es
    inicio + días − 1: una de 30 días desde el 3/11 termina el 2/12 y se vuelve
    a pedir el 3/12. Con inicio + días serían 31."""
    dias = dias or Parametros.cargar().dias_sancion
    return inicio + timedelta(days=dias - 1)


def aplicar(usuario, motivo, quien, inicio=None, termino=None):
    """US-12: sanciona a una persona y le avisa por correo.

    Es la única entrada para crear una desde el código, también para la
    sanción automática por inasistencias cuando se decida (US-12 AC8). Sin
    fechas, empieza hoy y dura `dias_sancion`. `full_clean()` revisa el motivo,
    que el término no sea anterior al inicio, que no empiece en el futuro
    (US-10, decidido el 20/10) y que no se cruce con otra no levantada.

    Esa última regla es una lectura y luego una escritura: dos administradores
    a la vez la pasarían los dos. Por eso todo corre en una transacción que
    bloquea antes la fila de la persona; el segundo espera al primero y ya ve
    su sanción. El correo sale solo si la sanción quedó guardada.
    """
    inicio = inicio or timezone.localdate()
    if termino is None:
        termino = termino_por_defecto(inicio)
    with transaction.atomic():
        Usuario.objects.select_for_update().filter(pk=usuario.pk).values_list("pk", flat=True).get()
        sancion = Sancion(usuario=usuario, motivo=(motivo or "").strip(), inicio=inicio, termino=termino,
                          creada_por=quien)
        sancion.full_clean()
        sancion.save()
        transaction.on_commit(partial(_avisar_sancion, sancion), robust=True)
    return sancion


def _avisar_sancion(sancion):
    persona = sancion.usuario
    avisar(
        persona.email,
        "Tienes una sanción en la sala de grabación",
        "notificaciones/sancion.txt",
        {"nombre": persona.get_full_name() or persona.email, "sancion": sancion},
    )
