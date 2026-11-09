"""US-08 AC8 y AC9: cuentas en lote desde una planilla CSV.

Se lee, se revisa fila por fila contra la base y recién al confirmar se guarda,
todo o nada. Una cuenta que ya existe solo suma roles y áreas: la planilla nunca
le quita nada. CSV y no Excel para no sumar una dependencia: Excel lo exporta
con "Guardar como → CSV".
"""
import csv
import io
import secrets
import unicodedata
from dataclasses import dataclass, field

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from . import services
from .models import Area, Rol, Usuario

COLUMNAS = ["correo", "nombre", "apellido", "roles", "areas"]
MAX_FILAS = 1000
MAX_BYTES = 1_000_000


def _normal(texto):
    """Sin tildes, en minúsculas y con un solo espacio: «Educación  Continua» y
    «educacion continua» son la misma área."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


ROLES = {_normal(rol.value): rol for rol in Rol} | {"apoyo": Rol.APOYO}


def plantilla():
    """La cabecera con punto y coma y BOM: así Excel en español la abre en columnas."""
    return "﻿" + ";".join(COLUMNAS) + "\r\n"


def leer(contenido):
    """Las filas del archivo como diccionarios con su número de fila. Falla con un
    mensaje para quien subió el archivo si no se puede leer."""
    if len(contenido) > MAX_BYTES:
        raise ValidationError("El archivo pesa más de 1 MB. Divídelo en varias planillas.")
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        # "CSV (delimitado por comas)" de Excel en Windows.
        texto = contenido.decode("cp1252", errors="replace")
    primera = texto.split("\n", 1)[0]
    separador = ";" if primera.count(";") >= primera.count(",") else ","
    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    cabecera = [_normal(c) for c in next(lector, [])]
    faltan = [c for c in COLUMNAS if c not in cabecera]
    if faltan:
        raise ValidationError(
            f"Faltan columnas: {', '.join(faltan)}. Usa la plantilla: {';'.join(COLUMNAS)}."
        )
    filas = []
    for numero, celdas in enumerate(lector, start=2):
        valores = {c: (celdas[cabecera.index(c)] if cabecera.index(c) < len(celdas) else "").strip() for c in COLUMNAS}
        if any(valores.values()):
            filas.append({"fila": numero, **valores})
    if not filas:
        raise ValidationError("La planilla no tiene filas con cuentas.")
    if len(filas) > MAX_FILAS:
        raise ValidationError(f"La planilla tiene más de {MAX_FILAS} cuentas. Divídela en varias.")
    return filas


def _lista(celda):
    return [parte.strip() for parte in celda.replace(";", ",").split(",") if parte.strip()]


@dataclass
class Fila:
    fila: int
    correo: str
    nombre: str
    apellido: str
    roles: list = field(default_factory=list)
    areas: list = field(default_factory=list)
    cuenta: Usuario | None = None
    suma_roles: list = field(default_factory=list)
    suma_areas: list = field(default_factory=list)
    errores: list = field(default_factory=list)

    @property
    def accion(self):
        if self.errores:
            return "error"
        if self.cuenta is None:
            return "crear"
        return "actualizar" if self.suma_roles or self.suma_areas else "sin cambios"


def revisar(crudas, quien):
    """Qué pasaría con cada fila si se confirma. No guarda nada."""
    areas = {_normal(a.nombre): a for a in Area.objects.all()}
    existentes = {
        u.email: u for u in Usuario.objects.filter(email__in=[c["correo"].lower() for c in crudas])
        .prefetch_related("groups", "areas")
    }
    vistos = {}
    filas = []
    for cruda in crudas:
        fila = Fila(cruda["fila"], cruda["correo"].lower(), cruda["nombre"], cruda["apellido"])
        filas.append(fila)
        errores = fila.errores

        if not fila.correo:
            errores.append("Falta el correo.")
        else:
            try:
                validate_email(fila.correo)
            except ValidationError:
                errores.append("Ese correo no es válido.")
            if fila.correo in vistos:
                errores.append(f"El correo ya está en la fila {vistos[fila.correo]}.")
            vistos.setdefault(fila.correo, fila.fila)
        for columna, campo in (("correo", "email"), ("nombre", "first_name"), ("apellido", "last_name")):
            largo = Usuario._meta.get_field(campo).max_length
            if len(cruda[columna]) > largo:
                errores.append(f"El {columna} pasa de {largo} caracteres.")

        rol_con_error = False
        for nombre in _lista(cruda["roles"]):
            rol = ROLES.get(_normal(nombre))
            if rol is None:
                rol_con_error = True
                errores.append(f"No existe el rol «{nombre}».")
            elif rol not in fila.roles:
                fila.roles.append(rol)
        area_con_error = False
        for nombre in _lista(cruda["areas"]):
            area = areas.get(_normal(nombre))
            if area is None or not area.activa:
                area_con_error = True
                errores.append(f"No existe el área «{nombre}»." if area is None
                               else f"El área «{area.nombre}» está desactivada.")
            elif area not in fila.areas:
                fila.areas.append(area)

        cuenta = fila.cuenta = existentes.get(fila.correo)
        tiene_roles = {g.name for g in cuenta.groups.all()} if cuenta else set()
        tiene_areas = set(cuenta.areas.all()) if cuenta else set()
        fila.suma_roles = [r for r in fila.roles if r not in tiene_roles]
        fila.suma_areas = [a for a in fila.areas if a not in tiene_areas]
        roles_finales = tiene_roles | set(fila.roles)

        if cuenta is None:
            if not fila.nombre:
                errores.append("Falta el nombre.")
            if not _lista(cruda["roles"]):
                errores.append("Elige al menos un rol.")
        elif not services.puede_cambiar_cuenta(cuenta, quien):
            errores.append("Es la cuenta de otro administrador: solo el superusuario la cambia.")
        if Rol.ADMINISTRADOR in fila.suma_roles and not quien.is_superuser:
            errores.append("Solo el superusuario da el rol de administrador.")
        # Un error en la causa no se repite como error en la consecuencia.
        if fila.areas and Rol.SOLICITANTE not in roles_finales and not rol_con_error:
            errores.append("Solo los solicitantes tienen área: agrega el rol Solicitante o quita las áreas.")
        # Solo cuando la planilla da el rol: lo que la cuenta ya traía no frena la carga.
        da_solicitante = Rol.SOLICITANTE in fila.suma_roles
        if da_solicitante and not area_con_error and not any(a.activa for a in tiene_areas | set(fila.areas)):
            errores.append("Un solicitante necesita al menos un área activa para pedir la sala.")
    return filas


def aplicar(crudas, quien):
    """Guarda todas las filas o ninguna, anota cada cambio (AC10) y manda el correo
    para crear la contraseña a las cuentas nuevas (AC9)."""
    with transaction.atomic():
        filas = revisar(crudas, quien)
        if any(f.errores for f in filas):
            raise ValidationError("La planilla tiene filas con errores. Corrígela y vuelve a subirla.")
        grupos = {g.name: g for g in Group.objects.filter(name__in=Rol.values)}
        nuevas, actualizadas = [], 0
        for fila in filas:
            if fila.accion == "crear":
                cuenta = Usuario(email=fila.correo, first_name=fila.nombre, last_name=fila.apellido)
                cuenta.set_password(secrets.token_urlsafe(32))
                cuenta.save()
                antes = services.CUENTA_NUEVA
                nuevas.append(cuenta)
            elif fila.accion == "actualizar":
                cuenta = fila.cuenta
                antes = services.foto_de_cuenta(cuenta.pk)
                actualizadas += 1
            else:
                continue
            cuenta.groups.add(*(grupos[r] for r in fila.suma_roles))
            cuenta.areas.add(*fila.suma_areas)
            services.registrar_cambios_de_cuenta(cuenta, antes, quien)
    sin_correo = [c.email for c in nuevas if not services.enviar_acceso(c)]
    return {"creadas": len(nuevas), "actualizadas": actualizadas, "sin_correo": sin_correo}
