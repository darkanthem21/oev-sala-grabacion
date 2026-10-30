"""Formularios del editor y reglas de integridad del check-out."""

import re

from django import forms
from django.core.exceptions import ValidationError


def validar_secciones(secciones):
    if not isinstance(secciones, list) or not 1 <= len(secciones) <= 30:
        raise ValidationError("El listado debe tener entre 1 y 30 secciones.")
    identificadores = set()
    resultado = []

    def texto(valor, limite):
        if not isinstance(valor, str) or not valor.strip() or len(valor.strip()) > limite:
            raise ValidationError(f"Completa los títulos y preguntas (máximo {limite} caracteres).")
        return valor.strip()

    def identificador(valor):
        if not isinstance(valor, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", valor) or valor in identificadores:
            raise ValidationError("Las secciones y preguntas deben tener identificadores únicos válidos.")
        identificadores.add(valor)
        return valor

    for seccion in secciones:
        if not isinstance(seccion, dict):
            raise ValidationError("La sección no es válida.")
        preguntas = seccion.get("preguntas")
        if not isinstance(preguntas, list) or not 1 <= len(preguntas) <= 30:
            raise ValidationError("Cada sección debe tener entre 1 y 30 preguntas.")
        nueva = {"id": identificador(seccion.get("id")), "titulo": texto(seccion.get("titulo"), 160), "preguntas": []}
        for pregunta in preguntas:
            if not isinstance(pregunta, dict):
                raise ValidationError("La pregunta no es válida.")
            nueva["preguntas"].append({"id": identificador(pregunta.get("id")), "texto": texto(pregunta.get("texto"), 500)})
        resultado.append(nueva)
    return resultado


class EditorCheckoutForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    secciones = forms.JSONField(widget=forms.Textarea(attrs={"rows": 16}))

    def clean_secciones(self):
        return validar_secciones(self.cleaned_data["secciones"])


class CheckoutForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    hora_salida = forms.TimeField(label="Hora efectiva de salida", widget=forms.TimeInput(attrs={"type": "time"}))
    observaciones = forms.CharField(label="Observaciones finales", required=False, max_length=5000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, listado, **kwargs):
        super().__init__(*args, **kwargs)
        self.listado = listado
        self.initial["revision"] = listado.revision
        for seccion in listado.secciones:
            for pregunta in seccion["preguntas"]:
                clave = pregunta["id"]
                self.fields[f"respuesta_{clave}"] = forms.ChoiceField(label=pregunta["texto"], choices=[("si", "Sí"), ("no", "No")], widget=forms.RadioSelect)
                self.fields[f"observacion_{clave}"] = forms.CharField(label="Observación del incumplimiento", required=False, max_length=5000, widget=forms.Textarea(attrs={"rows": 2}))
                self.fields[f"foto_{clave}"] = forms.ImageField(label="Foto de integridad", required=False, widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}))

    def clean(self):
        datos = super().clean()
        if datos.get("revision") != self.listado.revision:
            raise ValidationError("El listado cambió mientras respondías. Recarga la página para revisar la versión vigente.")
        for seccion in self.listado.secciones:
            for pregunta in seccion["preguntas"]:
                clave = pregunta["id"]
                if datos.get(f"respuesta_{clave}") == "no":
                    if len(datos.get(f"observacion_{clave}", "")) < 10:
                        self.add_error(f"observacion_{clave}", "Describe el incumplimiento con al menos 10 caracteres.")
                    if not datos.get(f"foto_{clave}"):
                        self.add_error(f"foto_{clave}", "Adjunta una foto de integridad para esta respuesta No.")
                foto = datos.get(f"foto_{clave}")
                if foto and (foto.size > 5 * 1024 * 1024 or foto.image.format not in {"JPEG", "PNG", "WEBP"}):
                    self.add_error(f"foto_{clave}", "Usa una imagen JPEG, PNG o WebP de hasta 5 MB.")
        return datos

    @property
    def secciones(self):
        return [{"titulo": s["titulo"], "preguntas": [
            {"respuesta": self[f"respuesta_{p['id']}"], "observacion": self[f"observacion_{p['id']}"], "foto": self[f"foto_{p['id']}"]}
            for p in s["preguntas"]
        ]} for s in self.listado.secciones]
