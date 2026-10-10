import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from personas.models import Area, Rol

Usuario = get_user_model()


class EncabezadoPorPantallaTestCase(TestCase):
    """La barra del solicitante no se cuela en pantallas que traen su encabezado."""

    def test_configuracion_trae_solo_su_techo(self):
        admin = Usuario.objects.create_user(email="admin@uach.cl", password="x", is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("panel_bloques"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "barra-superior")
        self.assertContains(response, 'class="techo"', count=1)

    def test_calendario_publico_no_trae_barra_aunque_haya_sesion(self):
        usuario = Usuario.objects.create_user(email="docente@uach.cl", password="x")
        self.client.force_login(usuario)
        response = self.client.get(reverse("calendario"))
        self.assertNotContains(response, "barra-superior")

    def _solicitante(self):
        usuario = Usuario.objects.create_user(email="docente@uach.cl", password="x")
        usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        usuario.areas.add(Area.objects.create(nombre="Informática", activa=True))
        self.client.force_login(usuario)
        return usuario

    def _pestana_activa(self, response):
        """El texto de la pestaña marcada con aria-current."""
        html = response.content.decode()
        nav = html[html.index('class="pestanas"'):html.index("</nav>", html.index('class="pestanas"'))]
        activas = re.findall(r'aria-current="page">([^<]+)</a>', nav)
        self.assertEqual(len(activas), 1, activas)
        return activas[0]

    def test_solicitante_usa_techo_con_pestanas(self):
        self._solicitante()
        response = self.client.get(reverse("mis_solicitudes"))
        self.assertContains(response, 'class="techo"', count=1)
        self.assertContains(response, f'href="{reverse("solicitar")}"')
        self.assertNotContains(response, "barra-superior")

    def test_pestana_activa_segun_la_pantalla(self):
        self._solicitante()
        casos = [
            (reverse("solicitar"), "Solicitar reserva"),
            (reverse("mis_solicitudes"), "Mis solicitudes"),
            (f'{reverse("mis_solicitudes")}?vista=anteriores', "Mis solicitudes"),
        ]
        for url, activa in casos:
            with self.subTest(url=url):
                self.assertEqual(self._pestana_activa(self.client.get(url)), activa)

    def test_seleccion_de_area_cuenta_como_solicitar(self):
        usuario = self._solicitante()
        usuario.areas.add(Area.objects.create(nombre="Medicina", activa=True))
        response = self.client.get(reverse("solicitar_area"))
        self.assertEqual(self._pestana_activa(response), "Solicitar reserva")
