"""US-10: levantar una sanción. Crearla es de la administración de Django.
US-05: guardar y desactivar áreas, con su registro de cambios."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Area, CambioArea, Sancion


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
