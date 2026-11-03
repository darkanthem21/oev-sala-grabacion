"""US-10 y US-12: aplicar y levantar sanciones.
US-05: guardar y desactivar áreas, con su registro de cambios."""
from datetime import timedelta
from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from configuracion.models import Parametros
from notificaciones.services import avisar

from .models import Area, CambioArea, Sancion, Usuario


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
