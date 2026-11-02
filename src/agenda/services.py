"""US-17 y jornada por semana: bloquear, levantar, quitar y cambiar bloques.
Las vistas no deciden, llaman acá.

Bloquear, quitar y cambiar un horario sacan horario. Las tres le preguntan a
`solicitudes` quién lo pierde (`afectadas`, por la señal `pedidos_vivos`) y, al
guardar, anuncian lo confirmado por `horario_quitado`: las pendientes se
rechazan y las aprobadas se cancelan, en la misma transacción.
"""
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format

from .models import Bloque, Bloqueo, Motivo, bloqueo_de
from .signals import horario_quitado, pedidos_vivos


def _vivos(ahora, **filtro):
    """Los pedidos vivos que todavía no empiezan: bloquear hoy a las 15:00 no le
    quita la sala a quien grabó en la mañana."""
    pedidos = [p for _, respuesta in pedidos_vivos.send(sender=Bloque, **filtro) for p in respuesta]
    return [p for p in pedidos if timezone.make_aware(datetime.combine(p.fecha, p.inicio)) > ahora]


def _orden(pedidos):
    return sorted(pedidos, key=lambda p: (p.fecha, p.inicio, p.codigo))


def afectadas(bloqueo, ahora=None):
    """Los pedidos que el bloqueo deja sin sala (AC4), pendientes y aprobados."""
    ahora = timezone.localtime(ahora)
    return _orden(
        p for p in _vivos(ahora, desde=bloqueo.desde, hasta=bloqueo.hasta)
        if bloqueo.cubre(p.fecha, p.inicio, p.bloque)
    )


def afectadas_bloque(bloque, fecha=None, ahora=None):
    """Los pedidos que pierde un bloque al quitarlo o cambiarle la hora: los de
    `fecha` si es solo esa semana, o todos los que vienen."""
    ahora = timezone.localtime(ahora)
    return _orden(_vivos(ahora, desde=fecha or ahora.date(), hasta=fecha, bloque=bloque.pk))


def fuera_de_jornada(bloque, fecha):
    """El bloqueo que saca un bloque de la plantilla solo esa fecha."""
    return Bloqueo(desde=fecha, hasta=fecha, bloque=bloque, motivo=Motivo.FUERA_DE_JORNADA)


def _horas(bloque):
    return f"de {bloque.inicio:%H:%M} a {bloque.termino:%H:%M}"


def nombre(bloque, fecha=None):
    """«el bloque de los martes de 09:40 a 11:00» o, solo esa semana, «el bloque
    del martes 14 de octubre de 09:40 a 11:00»."""
    if fecha is None:
        return f"el bloque de los {bloque.get_dia_display()} {_horas(bloque)}"
    return f"el bloque del {date_format(fecha, r'l j \d\e F')} {_horas(bloque)}"


def _anunciar(afectadas, razon, quien):
    if afectadas:
        horario_quitado.send(sender=Bloque, afectadas=afectadas, razon=razon, quien=quien)


@transaction.atomic
def bloquear(bloqueo, quien, afectadas=()):
    """Guarda el bloqueo; quienes pierden la sala se rechazan o se cancelan, con
    su correo (AC4 y AC6).

    `afectadas` son las que el administrador vio y confirmó. La vista se encarga
    de que sean las mismas que calcula `afectadas()`.
    """
    bloqueo.bloqueado_por = quien
    bloqueo.full_clean()
    bloqueo.save()
    _anunciar(afectadas, f"La sala estará bloqueada {bloqueo.periodo}, {bloqueo.alcance}: {bloqueo.razon}.", quien)
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


@transaction.atomic
def quitar(bloque, quien, afectadas=(), fecha=None):
    """Saca el bloque de la jornada: de todas las semanas, o solo de `fecha`.

    Uno de plantilla sale de una sola fecha con un bloqueo «fuera de jornada»;
    uno que ya era solo de esa fecha se desactiva. Nunca se borra.
    """
    if fecha is not None and bloque.fecha is None:
        ya = bloqueo_de(fecha, bloque.inicio, bloque.pk)
        if ya is not None:
            raise ValidationError(f"Ese día ya está bloqueado: {ya.razon}.")
        return bloquear(fuera_de_jornada(bloque, fecha), quien, afectadas)
    bloque.activo = False
    bloque.save(update_fields=["activo"])
    _anunciar(afectadas, f"{nombre(bloque, bloque.fecha).capitalize()} salió de la jornada.", quien)
    return None


@transaction.atomic
def cambiar(bloque, inicio, termino, quien, afectadas=(), fecha=None):
    """Otro horario para el bloque, en todas las semanas o solo en `fecha`.

    No se edita en el lugar: el viejo se desactiva (o, si es de plantilla y el
    cambio es de una semana, se saca esa fecha) y se crea otro. Así las reservas
    que ya pasaron siguen diciendo la hora que tuvieron. Si el nuevo choca con
    algo, `full_clean` lo dice y la transacción deshace todo.
    """
    semana = bloque.fecha or fecha
    if bloque.fecha is None and fecha is not None:
        if bloqueo_de(fecha, bloque.inicio, bloque.pk) is None:
            omitido = fuera_de_jornada(bloque, fecha)
            omitido.bloqueado_por = quien
            omitido.full_clean()
            omitido.save()
    else:
        bloque.activo = False
        bloque.save(update_fields=["activo"])
    nuevo = Bloque(dia=bloque.dia, inicio=inicio, termino=termino, fecha=semana)
    nuevo.full_clean()
    nuevo.save()
    _anunciar(
        afectadas,
        f"{nombre(bloque, semana).capitalize()} cambió de horario: ahora es {_horas(nuevo)}.",
        quien,
    )
    return nuevo


def validar_cambio(bloque, inicio, termino, fecha=None):
    """Si el cambio de horario entraría, sin guardar nada: lo hace y lo deshace.

    Así la lista de afectadas solo se muestra para un cambio que se puede
    guardar, con las mismas reglas que `cambiar` (cruces, restricción única).
    """
    with transaction.atomic():
        cambiar(Bloque.objects.get(pk=bloque.pk), inicio, termino, None, (), fecha)
        transaction.set_rollback(True)


@transaction.atomic
def reponer_semana(bloqueo, quien):
    """Devuelve a su fecha un bloque de plantilla que se había sacado solo esa
    semana. Si en su lugar se puso otro, hay que quitar ese primero."""
    bloque = bloqueo.bloque
    choca = Bloque.objects.filter(
        activo=True, fecha=bloqueo.desde, inicio__lt=bloque.termino, termino__gt=bloque.inicio
    ).first()
    if choca is not None:
        raise ValidationError(
            f"Esa semana está {nombre(choca, choca.fecha)}: quítalo antes de reponer este."
        )
    return levantar(bloqueo, quien, "Se repuso en la jornada de esa semana.")
