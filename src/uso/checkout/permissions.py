from personas.models import Rol


def es_apoyo(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.APOYO)


def es_administrador(usuario):
    return usuario.is_authenticated and usuario.es_administrador


def puede_consultar(usuario):
    """Reportes y evidencias: personal de apoyo o administración."""
    return es_apoyo(usuario) or es_administrador(usuario)
