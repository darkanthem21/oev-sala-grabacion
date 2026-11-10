from django import forms
from django.db.models import Q

from .models import Area, Rol, Usuario


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


class UsuarioForm(forms.ModelForm):
    """US-08 AC2: nombre, correo, al menos un rol y sus áreas. Los roles no son un
    campo del modelo (son grupos), así que los guarda el servicio."""

    roles = forms.MultipleChoiceField(choices=Rol.choices, widget=forms.CheckboxSelectMultiple, required=False)

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "areas"]
        labels = {"first_name": "Nombre", "last_name": "Apellido", "email": "Correo"}
        widgets = {"areas": forms.CheckboxSelectMultiple}
        error_messages = {
            "first_name": {"required": "Escribe el nombre."},
            "email": {"required": "Escribe el correo.", "invalid": "Ese correo no es válido."},
        }

    def __init__(self, *args, da_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        # El rol de administrador lo da y lo quita solo el superusuario: a los
        # demás no se les ofrece, y `clean_roles` lo conserva si ya estaba.
        self.admin_fijo = bool(not da_admin and self.instance.pk and self.instance.tiene_rol(Rol.ADMINISTRADOR))
        if not da_admin:
            self.fields["roles"].choices = [c for c in Rol.choices if c[0] != Rol.ADMINISTRADOR]
        # Un área desactivada no se ofrece, pero quien ya la tiene no la pierde
        # por guardar otro cambio.
        tiene = self.instance.areas.all() if self.instance.pk else Area.objects.none()
        self.fields["areas"].queryset = Area.objects.filter(Q(activa=True) | Q(pk__in=tiene)).order_by("nombre")
        if self.instance.pk:
            tiene_roles = self.instance.groups.values_list("name", flat=True)
            self.initial["roles"] = [rol for rol in tiene_roles if da_admin or rol != Rol.ADMINISTRADOR]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya hay una cuenta con ese correo.")
        return email

    def clean_roles(self):
        roles = self.cleaned_data["roles"]
        if self.admin_fijo:
            roles = [*roles, Rol.ADMINISTRADOR]
        if not roles:
            raise forms.ValidationError("Elige al menos un rol.")
        return roles
