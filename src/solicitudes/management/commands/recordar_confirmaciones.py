from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from solicitudes.services import recordar_confirmaciones


class Command(BaseCommand):
    help = (
        "US-03: manda el recordatorio de confirmar a las reservas aceptadas que entraron "
        "al plazo. Se puede correr las veces que sea: nadie recibe dos."
    )

    def handle(self, *args, **options):
        avisadas = recordar_confirmaciones(settings.URL_BASE)
        self.stdout.write(f"{timezone.localtime():%Y-%m-%d %H:%M} recordatorios enviados: {avisadas}")
