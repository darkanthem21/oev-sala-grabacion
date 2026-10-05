from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory

from personas.models import Area

from .services import obtener_bloques_dia_para_usuario
from .wizard import obtener_limites_reserva

# T4. En sala entran como máximo 5 personas: el solicitante y hasta 4 invitados.
# Los datos del solicitante vienen precargados de su cuenta (US-14 AC5); de cada
# invitado se pide nombre y correo, así que las filas de acompañante son una
# menos que el tope.
MAXIMO_PERSONAS = 5
MAXIMO_ACOMPANANTES = MAXIMO_PERSONAS - 1


def primer_error(form):
    """El primer mensaje de error del formulario: las pantallas del asistente
    muestran uno solo, arriba."""
    for errores in form.errors.values():
        return errores[0]
    return None


class IdsField(forms.Field):
    """Una lista de ids enteros que llega repetida en el formulario (bloques=1&bloques=2)."""

    widget = forms.MultipleHiddenInput

    def to_python(self, value):
        if not value:
            return []
        try:
            return list(dict.fromkeys(int(v) for v in value))
        except (TypeError, ValueError):
            raise ValidationError("Los bloques seleccionados no son válidos.", code="invalid")


class FechaReservaForm(forms.Form):
    """Un día pedible: con formato ISO y dentro de los límites de reserva.

    Es la única validación de fecha del calendario y del asistente; antes
    estaba copiada en cada vista.
    """

    fecha = forms.DateField(
        input_formats=["%Y-%m-%d"],
        error_messages={
            "required": "Por favor, selecciona un día disponible en el calendario.",
            "invalid": "Por favor, selecciona un día disponible en el calendario.",
        },
    )

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        fecha_minima, fecha_maxima = obtener_limites_reserva()
        if not fecha_minima <= fecha <= fecha_maxima:
            raise ValidationError(
                "La fecha seleccionada no está dentro del período permitido.", code="fuera_de_periodo"
            )
        return fecha

    @classmethod
    def fecha_de(cls, texto):
        """La fecha si el texto es un día pedible, o None."""
        form = cls({"fecha": texto})
        return form.cleaned_data["fecha"] if form.is_valid() else None


class SeleccionHorarioForm(FechaReservaForm):
    """Paso 1: el día y los bloques, que tienen que estar libres para el usuario.

    Con exigir_todos (el asistente) basta un bloque tomado para rechazar la
    selección; sin él (el calendario público) se acepta lo que siga libre.
    Si es válido, cleaned_data["bloques"] son los bloques del día elegidos.
    """

    bloques = IdsField(
        error_messages={"required": "Por favor, selecciona al menos un bloque de horario para continuar."},
    )

    def __init__(self, *args, usuario=None, exigir_todos=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.exigir_todos = exigir_todos

    @property
    def ids_enviados(self):
        """Los ids tal como llegaron, para volver a marcarlos si hay un error."""
        return [int(v) for v in self.data.getlist("bloques") if v.isdigit()] if self.data else []

    def clean(self):
        datos = super().clean()
        fecha, ids = datos.get("fecha"), datos.get("bloques")
        if fecha and ids:
            # disponible_para_reserva deja fuera también los que el usuario
            # ya tiene pendientes, igual que la pantalla.
            libres = [
                b for b in obtener_bloques_dia_para_usuario(fecha=fecha, usuario=self.usuario)
                if b.id in ids and b.disponible_para_reserva
            ]
            if self.exigir_todos and len(libres) != len(ids):
                raise ValidationError(
                    "Uno o más de los bloques seleccionados ya no están disponibles. Por favor, selecciona otros."
                )
            if not libres:
                raise ValidationError("Ninguno de los bloques seleccionados está disponible.")
            datos["bloques"] = libres
        return datos


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
