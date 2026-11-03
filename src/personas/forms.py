from django import forms

from .models import Area


class LevantarSancionForm(forms.Form):
    """US-10: levantar una sanción también queda con su motivo, como un bloqueo."""

    motivo = forms.CharField(
        max_length=200,
        error_messages={"required": "Escribe por qué se levanta la sanción."},
    )


class AplicarSancionForm(forms.Form):
    """US-12: lo que el administrador escribe para sancionar. Las reglas de las
    fechas no van acá: las revisa services.aplicar con `full_clean()`, así valen
    igual para la sanción automática cuando llegue."""

    motivo = forms.CharField(
        max_length=300,
        error_messages={"required": "Escribe el motivo de la sanción: le llega a la persona."},
    )
    inicio = forms.DateField(label="Desde", input_formats=["%Y-%m-%d"],
                             widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    termino = forms.DateField(label="Hasta (incluido)", input_formats=["%Y-%m-%d"],
                              widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))


class AreaForm(forms.ModelForm):
    """US-05 AC2: crear un área o cambiarle el nombre y la nota."""

    class Meta:
        model = Area
        fields = ["nombre", "nota"]
        error_messages = {"nombre": {"required": "Escribe el nombre del área."}}

    def clean_nombre(self):
        """El índice único distingue mayúsculas, y «instituto de informática» al
        lado de «Instituto de Informática» serían dos áreas para la misma gente."""
        nombre = self.cleaned_data["nombre"]
        if Area.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un área con ese nombre.")
        return nombre
