from datetime import date, time
from django.core.exceptions import ValidationError
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


class BloqueValidacionesTestCase(TestCase):
    def setUp(self):
        self.bloque_base = Bloque.objects.create(
            fecha=date(2026, 9, 21),
            hora_inicio=time(10, 0),
            hora_final=time(11, 0),
            disponible=True,
        )

    def test_hora_inicio_igual_o_posterior_a_hora_final_rechazada(self):
        with self.assertRaises(ValidationError):
            Bloque.objects.create(
                fecha=date(2026, 9, 21),
                hora_inicio=time(14, 0),
                hora_final=time(14, 0),
            )

        with self.assertRaises(ValidationError):
            Bloque.objects.create(
                fecha=date(2026, 9, 21),
                hora_inicio=time(15, 0),
                hora_final=time(14, 0),
            )

    def test_solapamiento_identico_rechazado(self):
        with self.assertRaises(ValidationError):
            Bloque.objects.create(
                fecha=date(2026, 9, 21),
                hora_inicio=time(10, 0),
                hora_final=time(11, 0),
            )

    def test_solapamiento_parcial_inicio_rechazado(self):
        # 09:30 - 10:30 se solapa con 10:00 - 11:00
        with self.assertRaises(ValidationError):
            Bloque.objects.create(
                fecha=date(2026, 9, 21),
                hora_inicio=time(9, 30),
                hora_final=time(10, 30),
            )

    def test_solapamiento_parcial_fin_rechazado(self):
        # 10:30 - 11:30 se solapa con 10:00 - 11:00
        with self.assertRaises(ValidationError):
            Bloque.objects.create(
                fecha=date(2026, 9, 21),
                hora_inicio=time(10, 30),
                hora_final=time(11, 30),
            )

    def test_solapamiento_envolvente_rechazado(self):
        # 09:00 - 12:00 contiene completamente a 10:00 - 11:00
        with self.assertRaises(ValidationError):
            Bloque.objects.create(
                fecha=date(2026, 9, 21),
                hora_inicio=time(9, 0),
                hora_final=time(12, 0),
            )

    def test_solapamiento_contenido_rechazado(self):
        # 10:15 - 10:45 está contenido dentro de 10:00 - 11:00
        with self.assertRaises(ValidationError):
            Bloque.objects.create(
                fecha=date(2026, 9, 21),
                hora_inicio=time(10, 15),
                hora_final=time(10, 45),
            )

    def test_bloques_adyacentes_mismo_dia_permitidos(self):
        # 09:00 - 10:00 y 11:00 - 12:00 son contiguos pero no se solapan con 10:00 - 11:00
        b_prev = Bloque.objects.create(
            fecha=date(2026, 9, 21),
            hora_inicio=time(9, 0),
            hora_final=time(10, 0),
        )
        self.assertIsNotNone(b_prev.id)

        b_post = Bloque.objects.create(
            fecha=date(2026, 9, 21),
            hora_inicio=time(11, 0),
            hora_final=time(12, 0),
        )
        self.assertIsNotNone(b_post.id)

    def test_mismo_horario_en_fechas_distintas_permitido(self):
        b_otro_dia = Bloque.objects.create(
            fecha=date(2026, 9, 22),
            hora_inicio=time(10, 0),
            hora_final=time(11, 0),
        )
        self.assertIsNotNone(b_otro_dia.id)

    def test_edicion_sin_cambio_de_horario_no_falla_por_solapamiento(self):
        self.bloque_base.disponible = False
        self.bloque_base.save()
        self.bloque_base.refresh_from_db()
        self.assertFalse(self.bloque_base.disponible)

    def test_bloque_en_fin_de_semana_permitido_en_modelo(self):
        # 2026-09-26 es sábado
        b_sabado = Bloque.objects.create(
            fecha=date(2026, 9, 26),
            hora_inicio=time(10, 0),
            hora_final=time(11, 0),
        )
        self.assertIsNotNone(b_sabado.id)

