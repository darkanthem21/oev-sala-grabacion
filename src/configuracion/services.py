from django.db import transaction

from .models import CambioParametro


def _legible(form, campo, valor):
    """Un campo con opciones guarda un número, y anotarlo crudo dejaría la
    bitácora diciendo "3 → 4"."""
    opciones = form.instance._meta.get_field(campo).choices
    return dict(opciones).get(valor, valor) if opciones else valor


@transaction.atomic
def guardar(form, quien):
    """Guarda los parámetros y anota en la bitácora lo que cambió (AC4).

    Atómico porque una configuración cambiada sin registro es lo que el criterio
    pide evitar. `changed_data` deja fuera lo que no cambió, así que volver a
    guardar sin tocar nada no ensucia el historial.
    """
    cambios = [
        CambioParametro(
            campo=campo,
            antes=str(_legible(form, campo, form.initial.get(campo, ""))),
            despues=str(_legible(form, campo, form.cleaned_data[campo])),
            quien=quien,
        )
        for campo in form.changed_data
    ]
    form.save()
    return CambioParametro.objects.bulk_create(cambios)
