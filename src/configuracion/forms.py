from django import forms

from .models import Parametros

# Etiqueta, controles y descripcion de cada fila del panel. La descripcion dice
# que hace el sistema con el valor; de donde salio el numero es cosa de
# `models.py`.
SECCIONES = [
    ("Recepción de solicitudes", [
        ("Límite para pedir", ["pedir_dia", "pedir_hora"],
         "Pasado ese momento la fecha más cercana que se puede pedir se corre una "
         "semana. Las solicitudes que ya llegaron se resuelven igual."),
        ("Desfase mínimo", ["semanas_desfase"],
         "Semanas completas entre la solicitud y la fecha pedida. Con 1, lo que se "
         "pide esta semana es para dentro de dos."),
    ]),
    ("Reserva", [
        ("Confirmación previa", ["plazo_confirmacion_dias"],
         "Cuándo se le pide al solicitante que confirme su asistencia. Si no responde, "
         "el bloque se libera."),
        ("Tope mensual por persona", ["tope_mensual"],
         "Por encima del tope la solicitud no se rechaza: llega marcada al validador, "
         "que decide si lo respeta."),
        ("Bloques por solicitud", ["max_bloques_solicitud"],
         "Una solicitud genera un ticket por cada bloque que pide. Por encima de este "
         "número también llega marcada."),
    ]),
    ("Cierre y sanciones", [
        ("Inasistencias para sancionar", ["inasistencias_para_sancion"],
         "Inasistencias seguidas tras las que el sistema sanciona solo. El administrador "
         "puede levantar o acortar una sanción después."),
        ("Duración de la sanción", ["dias_sancion"],
         "Cuánto impide pedir nuevas reservas. No cancela las que ya estaban aprobadas."),
    ]),
    ("Acceso", [
        ("Intentos antes de bloquear", ["intentos_maximos"],
         "Contraseñas erradas seguidas que bloquean la cuenta."),
        ("Duración del bloqueo", ["minutos_bloqueo"],
         "Cuánto dura ese bloqueo. Es temporal para que nadie pueda dejar a otra persona "
         "fuera del sistema a propósito."),
    ]),
]

# Va pegada al ultimo control de la fila: "8" no dice nada, "8 bloques" si.
UNIDADES = {
    "semanas_desfase": "semanas",
    "plazo_confirmacion_dias": "días antes",
    "tope_mensual": "bloques al mes",
    "max_bloques_solicitud": "bloques",
    "inasistencias_para_sancion": "inasistencias",
    "dias_sancion": "días",
    "intentos_maximos": "intentos",
    "minutos_bloqueo": "minutos",
}


class ParametrosForm(forms.ModelForm):
    """Un campo por parametro. Los `min`/`max` del HTML salen de los validadores
    del modelo, asi que el rango se escribe una vez y manda el del servidor."""

    class Meta:
        model = Parametros
        fields = "__all__"
        widgets = {
            # `aria-label` porque comparte fila con el dia y el <label> visible
            # es de ese: es el unico control sin etiqueta propia. Sin `format` el
            # value sale con segundos y hay navegadores que lo descartan.
            "pedir_hora": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time", "step": 900, "aria-label": "Hora límite para pedir"},
            ),
            "terminos": forms.Textarea(attrs={"rows": 8}),
        }

    def secciones(self):
        """Las filas listas para dibujar. `terminos` no esta aca: es un texto
        largo y ocupa su propia tarjeta."""
        return [
            (titulo, [self._fila(*fila) for fila in filas])
            for titulo, filas in SECCIONES
        ]

    def _fila(self, etiqueta, campos, detalle):
        return {
            "etiqueta": etiqueta,
            "campos": [self[campo] for campo in campos],
            "unidad": UNIDADES.get(campos[-1], ""),
            "detalle": detalle,
            "errores": [error for campo in campos for error in self[campo].errors],
        }
