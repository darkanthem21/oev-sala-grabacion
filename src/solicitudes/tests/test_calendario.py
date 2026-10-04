from datetime import date, time
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque, Dia, primera_fecha_pedible
from personas.models import Area, Rol
from solicitudes.models import Solicitud, SolicitudBloque


class CalendarioSolicitudesTestCase(TestCase):
    def setUp(self):
        self.bloque_disponible = Bloque.objects.filter(dia=Dia.JUEVES, activo=True).first()
        self.user = get_user_model().objects.create_user(email="s1@uv.cl", password="123")
        self.user.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.client.force_login(self.user)

        # Usar una fecha válida respetando primera_fecha_pedible
        fecha_minima = primera_fecha_pedible()
        # Jueves de esa semana mínima
        self.fecha_prueba = fecha_minima + date.resolution * ((Dia.JUEVES - fecha_minima.weekday()) % 7)

    def test_vista_calendario(self):
        url = reverse("calendario")
        response = self.client.get(f"{url}?year={self.fecha_prueba.year}&month={self.fecha_prueba.month}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/calendario.html")
        self.assertContains(response, "Calendario de Disponibilidad")
        self.assertContains(response, "solicitudes/calendario.css")
        for dia in ["LUN", "MAR", "MIE", "JUE", "VIE", "SÁB", "DOM"]:
            self.assertContains(response, f">{dia}</th>")
        self.assertContains(response, f'href="?year={self.fecha_prueba.year}&month={self.fecha_prueba.month}&fecha={self.fecha_prueba.isoformat()}"')

    def test_vista_bloques_dia(self):
        url = reverse("bloques_dia")
        response = self.client.get(f"{url}?fecha={self.fecha_prueba.isoformat()}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/bloques_dia.html")
        self.assertContains(response, f"Bloques para el día {self.fecha_prueba.strftime('%d/%m/%Y')}")
        self.assertContains(response, f"{self.bloque_disponible.inicio.strftime('%H:%M')} - {self.bloque_disponible.termino.strftime('%H:%M')}")
        self.assertContains(response, "Disponible")
        self.assertContains(response, "bloque-seleccionable")
        self.assertContains(response, f'data-id="{self.bloque_disponible.id}"')
        self.assertContains(response, f'value="{self.bloque_disponible.id}"')

    def test_bloque_con_solicitud_aceptada_no_esta_disponible_en_bloques_dia(self):
        area = Area.objects.create(nombre="Área Test", activa=True)
        solicitud_aceptada = Solicitud.objects.create(
            solicitante=self.user,
            area=area,
            fecha=self.fecha_prueba,
            motivo="Motivo test",
            personas=1,
            estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
            estado_confirmacion=Solicitud.EstadoConfirmacion.CONFIRMADA,
        )
        SolicitudBloque.objects.create(
            solicitud=solicitud_aceptada,
            bloque=self.bloque_disponible,
        )

        url = reverse("bloques_dia")
        response = self.client.get(f"{url}?fecha={self.fecha_prueba.isoformat()}")
        self.assertEqual(response.status_code, 200)
        # El bloque ocupado no debe aparecer disponible para selección
        self.assertNotContains(response, f'value="{self.bloque_disponible.id}"')
