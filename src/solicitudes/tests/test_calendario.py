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
        self.assertNotContains(response, "solicitudes/calendario.js")
        for dia in ["LUN", "MAR", "MIE", "JUE", "VIE", "SÁB", "DOM"]:
            self.assertContains(response, f">{dia}</th>")
        self.assertContains(response, 'href="?year=2026&month=9&fecha=2026-09-20"')

    def test_vista_bloques_dia(self):
        url = reverse("bloques_dia")
        response = self.client.get(f"{url}?fecha=2026-09-20")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/bloques_dia.html")
        self.assertContains(response, "Bloques para el día 20/09/2026")
        self.assertContains(response, "10:00 - 11:00")
        self.assertContains(response, "Disponible")
        self.assertContains(response, "bloque-seleccionable")
        self.assertContains(response, f'data-id="{self.bloque_disponible.id}"')
        self.assertContains(response, f'value="{self.bloque_disponible.id}"')
        self.assertContains(response, "No disponible")

    def test_seleccion_dia_en_calendario(self):
        url = reverse("calendario")
        response = self.client.get(f"{url}?year=2026&month=9&fecha=2026-09-20")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bloques para el día 20/09/2026")
        self.assertContains(response, "10:00 - 11:00")
        self.assertContains(response, "selected")

    def test_confirmar_seleccion_post_sin_bloques(self):
        url = reverse("calendario")
        response = self.client.post(f"{url}?year=2026&month=9", {
            "fecha": "2026-09-20",
            "bloques": [],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Por favor, selecciona al menos un bloque disponible.")

    def test_confirmar_seleccion_post_con_bloques(self):
        url = reverse("calendario")
        response = self.client.post(f"{url}?year=2026&month=9", {
            "fecha": "2026-09-20",
            "bloques": [str(self.bloque_disponible.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Día seleccionado: 20/09/2026")
        self.assertContains(response, "10:00 - 11:00")

    def test_no_permite_navegar_a_mes_pasado(self):
        url = reverse("calendario")
        # Intentar acceder a un mes pasado (agosto 2026)
        response = self.client.get(f"{url}?year=2026&month=8")
        self.assertEqual(response.status_code, 200)
        # Debe reajustarse al mes actual (Septiembre 2026)
        self.assertContains(response, "Septiembre 2026")
        # El botón de mes anterior debe estar deshabilitado
        self.assertContains(response, 'class="btn-nav disabled" aria-disabled="true">&laquo; Anterior</span>')
        # Las opciones de meses pasados en select-mes deben estar deshabilitadas
        self.assertContains(response, 'disabled>Agosto</option>')

