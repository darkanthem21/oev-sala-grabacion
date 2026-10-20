from django import forms


class LevantarSancionForm(forms.Form):
    """US-10: levantar una sanción también queda con su motivo, como un bloqueo."""

    motivo = forms.CharField(
        max_length=200,
        error_messages={"required": "Escribe por qué se levanta la sanción."},
    )
