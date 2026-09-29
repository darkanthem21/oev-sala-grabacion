from django import forms
from django.forms import formset_factory

from personas.models import Area

# T4. En sala entran como maximo 5 personas: el solicitante y hasta 4 invitados.
# Los datos del solicitante vienen precargados de su cuenta (US-14 AC5); de cada
# invitado se pide nombre y correo, asi que las filas de acompanante son una
# menos que el tope.
MAXIMO_PERSONAS = 5
MAXIMO_ACOMPANANTES = MAXIMO_PERSONAS - 1


class SolicitudForm(forms.Form):
    """US-02 AC3: motivo, area academica y cantidad de personas.

    Sin modelo detras a proposito. Cual entidad guarda el estado —Solicitud o
    Ticket— es la decision abierta que bloquea el modelo de datos, y escribir
    aqui un ModelForm la cerraria de hecho sin que el equipo la haya discutido.
    """

    area = forms.ModelChoiceField(
        queryset=Area.objects.none(),
        label="Área académica",
        # US-14 AC3: se elige de la lista de areas registradas, nunca a mano.
        empty_label="Selecciona un área",
        error_messages={"required": "Indica para qué área es la grabación."},
    )
    motivo = forms.CharField(
        label="Motivo de la solicitud",
        max_length=300,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Ej.: grabación de cápsula para el módulo de Bases de Datos",
        }),
        error_messages={"required": "El motivo es obligatorio."},
    )
    personas = forms.IntegerField(
        label=f"Cantidad de personas en sala (máximo {MAXIMO_PERSONAS})",
        min_value=1,
        max_value=MAXIMO_PERSONAS,
        initial=1,
        # x-model.number deja que Alpine muestre solo las filas de acompanante
        # que hagan falta. Es comodidad de pantalla: quien decide cuantas filas
        # son obligatorias es la validacion del servidor, mas abajo.
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
    # AC10. El checkbox del navegador es un recordatorio; el que impide enviar
    # sin aceptar es este required, que corre en el servidor.
    acepta_terminos = forms.BooleanField(
        label="He leído y acepto los términos y condiciones de uso de la sala",
        error_messages={
            "required": "Tienes que aceptar los términos y condiciones para enviar la solicitud.",
        },
        widget=forms.CheckboxInput(attrs={"x-model": "acepta"}),
    )

    def __init__(self, *args, usuario=None, exigir_terminos=True, **kwargs):
        super().__init__(*args, **kwargs)
        # US-02 AC1 y AC4: solo las areas a las que pertenece, y solo las
        # activas (US-05 AC3 saca un area del formulario sin borrar historial).
        areas = Area.objects.none() if usuario is None else usuario.areas.filter(activa=True)
        self.fields["area"].queryset = areas
        # US-14 AC4: con una sola area no hay nada que elegir; con varias, si.
        if len(areas) == 1:
            self.fields["area"].initial = areas[0]
            self.fields["area"].empty_label = None

        if not exigir_terminos and "acepta_terminos" in self.fields:
            self.fields["acepta_terminos"].required = False


class AcompananteForm(forms.Form):
    """US-02 AC6: identificación de las personas en sala."""

    # Los campos son opcionales fila por fila porque el formulario siempre
    # renderiza el maximo de filas y esconde las que sobran. Cuales filas son
    # de verdad obligatorias depende de `personas`, y eso se resuelve en la
    # vista, que es la unica que ve los dos formularios a la vez.
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
