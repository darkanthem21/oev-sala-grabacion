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

    def test_pantallas_del_solicitante_conservan_su_barra(self):
        usuario = Usuario.objects.create_user(email="docente@uach.cl", password="x")
        usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        usuario.areas.add(Area.objects.create(nombre="Informática", activa=True))
        self.client.force_login(usuario)
        for nombre in ["solicitar", "mis_solicitudes"]:
            with self.subTest(pantalla=nombre):
                self.assertContains(self.client.get(reverse(nombre)), "barra-superior")
