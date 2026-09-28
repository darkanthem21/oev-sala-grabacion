from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from personas.models import Area
from personas.views import destino_tras_login

Usuario = get_user_model()


class LoginFlujoTestCase(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Educación Virtual", activa=True)
        self.usuario = Usuario.objects.create_user(
            email="docente@uach.cl",
            first_name="Docente",
            last_name="Prueba",
            password="clave-segura-123",
        )
        self.usuario.areas.add(self.area)

    def test_settings_login_redirect_url(self):
        self.assertEqual(settings.LOGIN_REDIRECT_URL, "/solicitar/")

    def test_destino_tras_login_por_defecto_es_solicitar(self):
        url_destino = destino_tras_login(self.usuario)
        self.assertEqual(url_destino, reverse("solicitar"))

    def test_login_htmx_redirige_a_solicitar(self):
        url = reverse("login")
        response = self.client.post(
            url,
            {"username": "docente@uach.cl", "password": "clave-segura-123"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get("HX-Redirect"), reverse("solicitar"))

    def test_login_estandar_redirige_a_solicitar(self):
        url = reverse("login")
        response = self.client.post(
            url,
            {"username": "docente@uach.cl", "password": "clave-segura-123"},
        )
        self.assertRedirects(response, reverse("solicitar"))

    def test_login_respeta_parametro_next_valido(self):
        url = reverse("login")
        next_destino = reverse("calendario")
        response = self.client.post(
            f"{url}?next={next_destino}",
            {"username": "docente@uach.cl", "password": "clave-segura-123"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get("HX-Redirect"), next_destino)

    def test_login_ignora_next_externo_o_inseguro(self):
        url = reverse("login")
        response = self.client.post(
            f"{url}?next=https://sitio-malicioso.com/robo",
            {"username": "docente@uach.cl", "password": "clave-segura-123"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get("HX-Redirect"), reverse("solicitar"))

    def test_login_ignora_next_panel_y_redirige_a_solicitar(self):
        url = reverse("login")
        response = self.client.post(
            f"{url}?next=/",
            {"username": "docente@uach.cl", "password": "clave-segura-123"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get("HX-Redirect"), reverse("solicitar"))

    def test_acceso_no_autenticado_a_solicitar_redirige_a_login(self):
        url_solicitar = reverse("solicitar")
        response = self.client.get(url_solicitar)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('login')}?next={url_solicitar}", response.url)

    def test_vista_panel_redirige_a_solicitar(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("panel"))
        self.assertRedirects(response, reverse("solicitar"))

    def test_usuario_autenticado_en_login_redirige_a_solicitar(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, reverse("solicitar"))
