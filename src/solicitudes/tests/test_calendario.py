from datetime import date, time
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque


class CalendarioSolicitudesTestCase(TestCase):
    def setUp(self):
        self.bloque_disponible = Bloque.objects.create(
            fecha=date(2026, 9, 20),
            hora_inicio=time(10, 0),
            hora_final=time(11, 0),
            disponible=True,
        )
        self.bloque_ocupado = Bloque.objects.create(
            fecha=date(2026, 9, 20),
            hora_inicio=time(11, 0),
            hora_final=time(12, 0),
            disponible=False,
        )

    def test_vista_calendario(self):
        url = reverse("calendario")
        response = self.client.get(f"{url}?year=2026&month=9")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/calendario.html")
        self.assertContains(response, "Calendario de Disponibilidad")
        self.assertContains(response, "Septiembre 2026")
        self.assertContains(response, "solicitudes/calendario.css")
        self.assertContains(response, "solicitudes/calendario.js")

    def test_vista_bloques_dia(self):
        url = reverse("bloques_dia")
        response = self.client.get(f"{url}?fecha=2026-09-20")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/bloques_dia.html")
        self.assertContains(response, "10:00 - 11:00")
        self.assertContains(response, "Disponible")
        self.assertContains(response, "bloque-seleccionable")
        self.assertContains(response, f'data-id="{self.bloque_disponible.id}"')
        self.assertContains(response, 'aria-pressed="false"')
        self.assertContains(response, "No disponible")
