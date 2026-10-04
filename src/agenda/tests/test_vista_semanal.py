"""US-17. La vista semanal dice qué semana es, se mueve entre semanas y raya los
bloques bloqueados en su fecha, sin dejar de avisar que la jornada es una sola."""
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque, Bloqueo, Dia


class VistaSemanal(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_user(
            email="admin@uach.cl", password="clave-de-prueba", is_staff=True
        )
        self.client.force_login(admin)
        # La migración ya carga la jornada por defecto: se usa ese bloque.
        self.bloque = Bloque.objects.filter(dia=Dia.MIERCOLES, activo=True).order_by("inicio").first()

    def semana(self, desde):
        return self.client.get(reverse("panel_bloques"), {"vista": "semana", "desde": desde})

    def test_el_titulo_dice_que_semana_es(self):
        respuesta = self.semana("2026-10-07")
        self.assertEqual(respuesta.context["titulo"], "Semana del 5 al 9 de octubre de 2026")

    def test_una_semana_entre_dos_meses_nombra_los_dos(self):
        respuesta = self.semana("2026-10-01")
        self.assertEqual(respuesta.context["titulo"], "Semana del 28 de septiembre al 2 de octubre de 2026")

    def test_se_mueve_de_a_una_semana(self):
        respuesta = self.semana("2026-10-07")
        self.assertEqual(respuesta.context["anterior"], date(2026, 9, 30))
        self.assertEqual(respuesta.context["siguiente"], date(2026, 10, 14))

    def test_un_domingo_hoy_lleva_a_la_semana_que_viene(self):
        with mock.patch("agenda.views.timezone.localdate", return_value=date(2026, 10, 4)):
            respuesta = self.client.get(reverse("panel_bloques"), {"vista": "semana"})
        self.assertEqual(respuesta.context["dias"][0]["fecha"], date(2026, 10, 5))

    def test_el_mini_calendario_marca_la_semana_elegida(self):
        respuesta = self.semana("2026-10-07")
        elegidos = [d["fecha"] for s in respuesta.context["mini"]["semanas"] for d in s if d["elegida"]]
        self.assertEqual(elegidos[0], date(2026, 10, 5))
        self.assertEqual(elegidos[-1], date(2026, 10, 11))

    def test_raya_el_bloque_bloqueado_solo_en_su_fecha(self):
        Bloqueo.objects.create(desde=date(2026, 10, 7), hasta=date(2026, 10, 7),
                               bloque=self.bloque, motivo=Bloqueo._meta.get_field("motivo").choices[0][0])
        miercoles = self.semana("2026-10-07").context["dias"][Dia.MIERCOLES]
        self.assertIn(self.bloque.pk, miercoles["bloqueados"])
        otro = self.semana("2026-10-14").context["dias"][Dia.MIERCOLES]
        self.assertNotIn(self.bloque.pk, otro["bloqueados"])

    def test_avisa_que_los_horarios_valen_para_todas_las_semanas(self):
        self.assertContains(self.semana("2026-10-07"), "todas las semanas")
