from django import forms

from .models import Bloque


class BloqueForm(forms.ModelForm):
    """Valida y nada mas: los campos los dibuja la plantilla, porque la duracion
    se calcula en el navegador y no es una columna.

    ModelForm y no `full_clean` a mano: si la hora viene rota, el formulario no la
    escribe en la instancia y `Bloque.clean()` sigue comparando horas, no texto.
    """

    class Meta:
        model = Bloque
        fields = ["inicio", "termino"]
