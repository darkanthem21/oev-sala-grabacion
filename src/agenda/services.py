"""US-17: bloquear y levantar. Las vistas no deciden, llaman acá."""
from collections import defaultdict
from datetime import datetime
from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from notificaciones.services import avisar

from .models import Bloqueo
from .signals import reservas_aprobadas


def afectadas(bloqueo, ahora=None):
    """Las reservas aprobadas que el bloqueo deja sin sala (AC4).

    No cuentan las que ya empezaron: bloquear hoy a las 15:00 no le quita la
    sala a quien grabó en la mañana.
    """
    ahora = timezone.localtime(ahora)
    respuestas = reservas_aprobadas.send(sender=Bloqueo, desde=bloqueo.desde, hasta=bloqueo.hasta)
    return sorted(
        (
            reserva
            for _, reservas in respuestas
            for reserva in reservas
            if bloqueo.cubre(reserva.fecha, reserva.inicio)
            and timezone.make_aware(datetime.combine(reserva.fecha, reserva.inicio)) > ahora
        ),
        key=lambda r: (r.fecha, r.inicio, r.codigo),
    )


@transaction.atomic
def bloquear(bloqueo, quien, avisar_a=()):
    """Guarda el bloqueo y avisa a quienes pierden su reserva (AC4 y AC6).

    `avisar_a` son las reservas afectadas que el administrador vio y confirmó.
    La vista se encarga de que sean las mismas que calcula `afectadas`.

    Los correos salen cuando la transacción se confirma: un bloqueo que no
    alcanzó a guardarse no puede haber avisado a nadie. Va uno por persona, con
    todas sus reservas, y si uno falla los demás igual salen.
    """
    bloqueo.bloqueado_por = quien
    bloqueo.full_clean()
    bloqueo.save()

    por_persona = defaultdict(list)
    for reserva in avisar_a:
        por_persona[reserva.correo].append(reserva)
    for correo, reservas in por_persona.items():
        transaction.on_commit(
            partial(
                avisar,
                correo,
                "Tu reserva de la sala de grabación no se podrá realizar",
                "notificaciones/bloqueo.txt",
                {"bloqueo": bloqueo, "reservas": reservas, "nombre": reservas[0].solicitante},
            ),
            robust=True,
        )
    return bloqueo


def levantar(bloqueo, quien, motivo):
    """El horario vuelve a estar disponible y queda anotado quién, cuándo y
    por qué (AC5 y AC6).

    Se levanta con un UPDATE condicionado, así dos administradores levantando
    el mismo bloqueo a la vez no pisan el registro del primero.
    """
    if bloqueo.hasta < timezone.localdate():
        raise ValidationError("Ese bloqueo ya pasó: no hay horario que devolver.")
    levantados = Bloqueo.objects.filter(pk=bloqueo.pk, levantado_en__isnull=True).update(
        levantado_por=quien, levantado_en=timezone.now(), motivo_levantamiento=motivo
    )
    if not levantados:
        raise ValidationError("Ese bloqueo ya estaba levantado.")
    bloqueo.refresh_from_db()
    return bloqueo
