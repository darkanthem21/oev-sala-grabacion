"""US-10: levantar una sanción. Crearla es de la administración de Django."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Sancion


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
