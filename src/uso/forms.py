from django import forms

from personas.models import Area

from .services import ESTADOS_SANCION


class FiltroSancionesForm(forms.Form):
    """US-12 T4: los filtros del listado de Sanciones.

    Por GET, como el historial de US-11: la dirección se puede compartir y la
    paginación los conserva. Todos son opcionales.
    """

    texto = forms.CharField(label="Persona", required=False, max_length=100,
                            widget=forms.TextInput(attrs={"placeholder": "Nombre o correo", "type": "search"}))
    # Las inactivas también: quien está en una sigue teniendo su historial.
    area = forms.ModelChoiceField(queryset=Area.objects.all(), label="Área", required=False, empty_label="Todas")
    estado = forms.ChoiceField(label="Estado de la sanción", required=False,
                               choices=[("", "Todos"), *ESTADOS_SANCION.items()])

    def datos(self):
        """Los filtros válidos; uno mal escrito se ignora y el formulario lo
        marca, en vez de dejar la tabla vacía."""
        self.is_valid()
        return {campo: self.cleaned_data.get(campo) for campo in ("area", "estado", "texto")}
