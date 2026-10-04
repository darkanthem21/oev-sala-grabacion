from django import forms

from .models import Bloque


class BloqueForm(forms.ModelForm):
    """Solo valida. Los campos los dibuja la plantilla porque la duración se
    calcula en el navegador y no es una columna.

    Es ModelForm para que una hora rota no llegue a la instancia y
    `Bloque.clean()` siga comparando horas en vez de texto.
    """

    class Meta:
        model = Bloque
        fields = ["inicio", "termino"]
