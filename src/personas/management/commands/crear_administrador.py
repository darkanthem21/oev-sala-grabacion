import secrets

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.urls import reverse

from personas.models import Rol, Usuario
from personas.services import enviar_acceso, foto_de_cuenta, registrar_cambios_de_cuenta


class Command(BaseCommand):
    help = (
        "US-08 AC11: deja la cuenta de soporte de la OEV como superusuario con el rol de "
        "administrador. Si no existe, la crea y le manda el correo para crear la contraseña. "
        "Se puede correr más de una vez."
    )

    def add_arguments(self, parser):
        parser.add_argument("correo")

    def handle(self, *args, correo, **options):
        correo = correo.strip().lower()
        try:
            validate_email(correo)
        except ValidationError:
            raise CommandError(f"«{correo}» no es un correo válido.")

        with transaction.atomic():
            usuario = Usuario.objects.filter(email__iexact=correo).first()
            nueva = usuario is None
            antes = foto_de_cuenta(None if nueva else usuario.pk)
            if nueva:
                # Como en la pestaña Usuarios: Django no manda el enlace de /clave/
                # a una cuenta sin contraseña usable.
                usuario = Usuario(email=correo)
                usuario.set_password(secrets.token_urlsafe(32))
            usuario.is_active = usuario.is_staff = usuario.is_superuser = True
            usuario.save()
            usuario.groups.add(Group.objects.get(name=Rol.ADMINISTRADOR))
            cambio = foto_de_cuenta(usuario.pk) != antes
            registrar_cambios_de_cuenta(usuario, antes, quien=None)

        if not nueva:
            estado = "ahora es" if cambio else "ya era"
            self.stdout.write(f"{correo} {estado} superusuario con el rol de administrador. Su contraseña no cambió.")
        elif enviar_acceso(usuario):
            self.stdout.write(f"Cuenta creada: {correo}. Le llegará un correo para crear su contraseña.")
        else:
            self.stdout.write(self.style.WARNING(
                f"Cuenta creada: {correo}, pero el correo no salió. Puede crear su contraseña en "
                f"{settings.URL_BASE}{reverse('password_reset')}."
            ))
