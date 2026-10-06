from django.apps import AppConfig


class SolicitudesConfig(AppConfig):
    name = "solicitudes"

    def ready(self):
        # Agenda pregunta por señal quién pierde la sala cuando saca horario, y
        # avisa por otra lo que se confirmó, porque importar este módulo desde
        # allá sería al revés.
        from agenda.signals import horario_quitado, pedidos_vivos

        from .services import liberar
        from .services import pedidos_vivos as receptor

        pedidos_vivos.connect(receptor, dispatch_uid="solicitudes.pedidos_vivos")
        horario_quitado.connect(liberar, dispatch_uid="solicitudes.liberar")
