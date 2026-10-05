from django.apps import AppConfig


class SolicitudesConfig(AppConfig):
    name = "solicitudes"

    def ready(self):
        # US-17 AC4. Agenda pregunta por señal quién pierde la sala con un
        # bloqueo, porque importar este módulo desde allá sería al revés.
        from agenda.signals import reservas_aprobadas

        from .services import reservas_aprobadas as receptor

        reservas_aprobadas.connect(receptor, dispatch_uid="solicitudes.reservas_aprobadas")
