from django import forms
from django.utils import timezone

from .models import Bloque, Bloqueo, bloqueos_por_fecha, disponibilidad


class BloqueForm(forms.ModelForm):
    """Solo valida. Los campos los dibuja la plantilla porque la duración se
    calcula en el navegador y no es una columna.

    Es ModelForm para que una hora rota no llegue a la instancia y
    `Bloque.clean()` siga comparando horas en vez de texto.
    """

    class Meta:
        model = Bloque
        fields = ["inicio", "termino"]


class HorasForm(forms.Form):
    """Las horas de un cambio de horario. El bloque nuevo lo valida
    `services.cambiar`, después de sacar el viejo, porque antes chocaría con él."""

    inicio = forms.TimeField()
    termino = forms.TimeField()


# US-17 AC1: un bloque, un día completo o un rango de fechas.
MODOS = [("dia", "Todo el día"), ("bloque", "Un bloque"), ("rango", "Varios días")]


class BloqueoForm(forms.ModelForm):
    """Lo que el administrador bloquea desde el panel, con su motivo (AC1).

    `modo` no es columna: dice cuáles de los otros campos valen. Los que no
    valen se descartan acá, porque el navegador también manda los ocultos.

    Las reglas que son solo del panel viven acá y no en `Bloqueo.clean()`, para
    que en la administración de Django se pueda corregir una fila vieja.
    """

    modo = forms.ChoiceField(choices=MODOS, initial="dia")

    class Meta:
        model = Bloqueo
        fields = ["desde", "hasta", "bloque", "motivo", "detalle"]
        error_messages = {
            "desde": {"required": "Indica qué día bloquear.",
                      "invalid": "Esa fecha no es válida."},
            "hasta": {"invalid": "Esa fecha no es válida."},
            "motivo": {"required": "Elige el motivo: mantención, feriado o evento."},
        }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "bq")
        super().__init__(*args, **kwargs)
        self.fields["bloque"].queryset = Bloque.objects.filter(activo=True)
        self.fields["hasta"].required = False

    def clean(self):
        datos = super().clean()
        modo, desde = datos.get("modo"), datos.get("desde")
        if modo != "rango":
            datos["hasta"] = desde
        elif not datos.get("hasta") and "hasta" not in self.errors:
            self.add_error("hasta", "Indica hasta qué día.")
        if modo != "bloque":
            datos["bloque"] = None
        elif not datos.get("bloque") and "bloque" not in self.errors:
            self.add_error("bloque", "Elige qué bloque.")

        if desde and desde < timezone.localdate():
            self.add_error("desde", "No se puede bloquear un día que ya pasó.")
        if self.errors:
            return datos

        hasta = datos.get("hasta")
        if hasta < desde:
            return datos  # `Bloqueo.clean()` lo explica mejor.
        # Si no queda nada que bloquear, la fila solo ensuciaría el registro. Es
        # también lo que frena un doble clic en «Bloquear».
        tentativo = Bloqueo(desde=desde, hasta=hasta, bloque=datos.get("bloque"))
        libres = disponibilidad(desde, hasta)
        if not any(tentativo.cubre(f, b.inicio, b.pk) for f, bloques in libres.items() for b in bloques):
            ya = next((x for xs in bloqueos_por_fecha(desde, hasta).values() for x in xs), None)
            if ya is None:
                raise forms.ValidationError(
                    "Esas fechas no tienen jornada: no hay nada que bloquear."
                )
            raise forms.ValidationError(f"Eso ya está bloqueado: {ya.razon}, {ya.periodo}.")
        return datos


class LevantarForm(forms.Form):
    """AC6: el levantamiento también queda con su motivo."""

    motivo = forms.CharField(
        max_length=200,
        error_messages={"required": "Escribe por qué se levanta el bloqueo."},
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "levantar")
        super().__init__(*args, **kwargs)
