from datetime import date, time
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque
from agenda.services import (
    obtener_bloques_dia,
    obtener_bloques_mes,
    obtener_dias_con_bloques_disponibles,
)


class AgendaServicesTestCase(TestCase):
    def setUp(self):
        self.b1 = Bloque.objects.create(
            fecha=date(2026, 9, 10),
            hora_inicio=time(9, 0),
            hora_final=time(10, 0),
            disponible=True,
        )
        self.b2 = Bloque.objects.create(
            fecha=date(2026, 9, 10),
            hora_inicio=time(10, 0),
            hora_final=time(11, 0),
            disponible=False,
        )
        self.b3 = Bloque.objects.create(
            fecha=date(2026, 9, 15),
            hora_inicio=time(14, 0),
            hora_final=time(15, 0),
            disponible=True,
        )

    def test_obtener_bloques_mes(self):
        bloques = list(obtener_bloques_mes(2026, 9, disponible=True))
        self.assertEqual(len(bloques), 2)
        self.assertIn(self.b1, bloques)
        self.assertIn(self.b3, bloques)

    def test_obtener_bloques_dia(self):
        bloques = list(obtener_bloques_dia(date(2026, 9, 10)))
        self.assertEqual(len(bloques), 2)
        self.assertEqual(bloques[0], self.b1)
        self.assertEqual(bloques[1], self.b2)

    def test_obtener_dias_con_bloques_disponibles(self):
        dias = obtener_dias_con_bloques_disponibles(2026, 9)
        self.assertEqual(dias, {10, 15})


class AgendaApiViewsTestCase(TestCase):
    def setUp(self):
        Bloque.objects.create(
            fecha=date(2026, 9, 10),
            hora_inicio=time(9, 0),
            hora_final=time(10, 0),
            disponible=True,
        )

    def test_api_bloques_dia(self):
        url = reverse("agenda_bloques_dia")
        response = self.client.get(f"{url}?fecha=2026-09-10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["fecha"], "2026-09-10")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["bloques"][0]["hora_inicio"], "09:00")

    def test_api_disponibilidad_mes(self):
        url = reverse("agenda_disponibilidad_mes")
        response = self.client.get(f"{url}?year=2026&month=9")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["dias_disponibles"], [10])

    def test_calendario_redirect(self):
        response = self.client.get("/agenda/calendario/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/solicitar/calendario/")
