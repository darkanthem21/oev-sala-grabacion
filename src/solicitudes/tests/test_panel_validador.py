"""US-07. Quién entra al panel del validador."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from personas.models import Rol


class AccesoAlPanel(TestCase):
    url = reverse("panel_validador")

    def test_el_validador_lo_ve(self):
        validador = get_user_model().objects.create_user("validador@prueba.local", "clave-larga-123")
        validador.groups.add(Group.objects.get(name=Rol.VALIDADOR))
        self.client.force_login(validador)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Datos de prueba")
        self.assertContains(respuesta, 'id="datos-panel"')

    def test_un_solicitante_no_entra(self):
        comun = get_user_model().objects.create_user("comun@prueba.local", "clave-larga-123")
        self.client.force_login(comun)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login_validacion"), respuesta["Location"])

    def test_sin_sesion_no_entra(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
