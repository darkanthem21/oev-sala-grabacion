"""Los avisos que el sistema le manda a las personas.

Por ahora cada aviso sale directo por correo, con el backend que diga
`settings.EMAIL_BACKEND` (en desarrollo, la consola). La bandeja de salida del
README llega cuando haga falta reintentar, y entonces cambia este archivo y
ningún otro.
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string


def avisar(correo, asunto, plantilla, contexto):
    """Un correo de texto plano a una persona, armado con una plantilla de
    `notificaciones/templates/notificaciones/`."""
    send_mail(asunto, render_to_string(plantilla, contexto), None, [correo])
