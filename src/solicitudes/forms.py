from django import forms
from django.forms import formset_factory

from personas.models import Area

# T4. En sala entran como máximo 5 personas: el solicitante y hasta 4 invitados.
# Los datos del solicitante vienen precargados de su cuenta (US-14 AC5); de cada
# invitado se pide nombre y correo, así que las filas de acompañante son una
# menos que el tope.
MAXIMO_PERSONAS = 5
MAXIMO_ACOMPANANTES = MAXIMO_PERSONAS - 1


class SeleccionAreaForm(forms.Form):
    """Paso previo: Selección de área académica para la solicitud de reserva."""

    area = forms.ModelChoiceField(
        queryset=Area.objects.none(),
        label="Área académica",
        empty_label="Selecciona un área académica",
        error_messages={"required": "Por favor, selecciona un área académica para continuar."},
        widget=forms.Select(attrs={"class": "select-personalizado"}),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        areas = Area.objects.none() if usuario is None else usuario.areas.filter(activa=True)
        self.fields["area"].queryset = areas
        if len(areas) == 1:
            self.fields["area"].initial = areas[0]
            self.fields["area"].empty_label = None


class SolicitudForm(forms.Form):
    """Paso 2: Motivo y cantidad de personas para la reserva."""

    motivo = forms.CharField(
        label="Motivo de la solicitud",
        max_length=300,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Ej.: grabación de cápsula para el módulo de Bases de Datos",
        }),
        error_messages={"required": "El motivo es obligatorio."},
    )
    observaciones = forms.CharField(
        label="Observaciones y requerimientos técnicos",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Opcional: iluminación, micrófonos, apoyo técnico…",
        }),
    )
    personas = forms.IntegerField(
        label=f"Cantidad de personas en sala (máximo {MAXIMO_PERSONAS})",
        min_value=1,
        max_value=MAXIMO_PERSONAS,
        initial=1,
        widget=forms.NumberInput(attrs={
            "min": 1,
            "max": MAXIMO_PERSONAS,
            "x-model.number": "personas",
        }),
        error_messages={
            "max_value": f"Como máximo {MAXIMO_PERSONAS} personas en sala.",
            "min_value": "Al menos tienes que entrar tú.",
        },
    )
    acepta_terminos = forms.BooleanField(
        label="He leído y acepto los términos y condiciones de uso de la sala",
        error_messages={
            "required": "Tienes que aceptar los términos y condiciones para enviar la solicitud.",
        },
        widget=forms.CheckboxInput(attrs={"x-model": "acepta"}),
    )

    def __init__(self, *args, usuario=None, exigir_terminos=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not exigir_terminos and "acepta_terminos" in self.fields:
            self.fields["acepta_terminos"].required = False


class AcompananteForm(forms.Form):
    """US-02 AC6: identificación de las personas en sala."""

    nombre = forms.CharField(label="Nombre", max_length=120, required=False)
    correo = forms.EmailField(label="Correo electrónico", required=False)

    def clean(self):
        datos = super().clean()
        nombre, correo = datos.get("nombre"), datos.get("correo")
        if nombre and not correo:
            self.add_error("correo", "Falta el correo de esta persona.")
        if correo and not nombre:
            self.add_error("nombre", "Falta el nombre de esta persona.")
        return datos

    @property
    def esta_lleno(self):
        return bool(self.cleaned_data.get("nombre") or self.cleaned_data.get("correo"))


AcompananteFormSet = formset_factory(
    AcompananteForm,
    extra=MAXIMO_ACOMPANANTES,
    max_num=MAXIMO_ACOMPANANTES,
    validate_max=True,
)
