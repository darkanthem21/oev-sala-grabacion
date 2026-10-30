from personas.models import Rol


def es_apoyo(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.APOYO)


def es_administrador(usuario):
    return usuario.is_authenticated and usuario.is_active and (
        usuario.is_staff or usuario.tiene_rol(Rol.ADMINISTRADOR)
    )
