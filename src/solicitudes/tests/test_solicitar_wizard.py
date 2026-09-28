from datetime import date, time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque
from personas.models import Area

Usuario = get_user_model()


class SolicitarWizardTestCase(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Informática", activa=True)
        self.usuario = Usuario.objects.create_user(
            email="docente@uach.cl",
            first_name="María",
            last_name="Docente",
            password="testpassword123",
        )
        self.usuario.areas.add(self.area)
        self.client.force_login(self.usuario)

        self.bloque = Bloque.objects.create(
            fecha=date(2026, 9, 20),
            hora_inicio=time(10, 0),
            hora_final=time(11, 0),
            disponible=True,
        )

    def test_acceso_paso1_por_defecto(self):
        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/solicitar.html")
        self.assertContains(response, "Paso 1: Selecciona fecha y horario")
        self.assertContains(response, "Horario y Disponibilidad")
        self.assertContains(response, 'hx-get="/solicitar/bloques/?fecha=2026-09-20"')
        self.assertContains(response, 'hx-push-url="false"')

    def test_paso1_post_sin_bloques_muestra_error(self):
        url = reverse("solicitar")
        response = self.client.post(f"{url}?paso=1", {
            "paso": "1",
            "fecha": "2026-09-20",
            "bloques": [],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Por favor, selecciona al menos un bloque disponible.")

    def test_paso1_post_con_bloques_avanza_a_paso2(self):
        url = reverse("solicitar")
        response = self.client.post(f"{url}?paso=1", {
            "paso": "1",
            "fecha": "2026-09-20",
            "bloques": [str(self.bloque.id)],
        })
        self.assertRedirects(response, f"{url}?paso=2")
        self.assertEqual(self.client.session.get("solicitud_reserva", {}).get("fecha"), "2026-09-20")
        self.assertEqual(self.client.session.get("solicitud_reserva", {}).get("bloques_ids"), [self.bloque.id])

    def test_paso2_muestra_resumen_horario(self):
        session = self.client.session
        session["solicitud_reserva"] = {
            "fecha": "2026-09-20",
            "bloques_ids": [self.bloque.id],
            "bloques_texto": "10:00 - 11:00",
        }
        session.save()

        url = reverse("solicitar")
        response = self.client.get(f"{url}?paso=2")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paso 2: Datos de la actividad")
        self.assertContains(response, "10:00 - 11:00")
        self.assertContains(response, "Informática")

    def test_paso2_post_valido_avanza_a_paso3(self):
        session = self.client.session
        session["solicitud_reserva"] = {
            "fecha": "2026-09-20",
            "bloques_ids": [self.bloque.id],
            "bloques_texto": "10:00 - 11:00",
        }
        session.save()

        url = reverse("solicitar")
        response = self.client.post(f"{url}?paso=2", {
            "paso": "2",
            "area": str(self.area.id),
            "motivo": "Grabación de cápsula educativa",
            "observaciones": "Micrófono corbatero",
            "personas": 1,
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "4",
        })
        self.assertRedirects(response, f"{url}?paso=3")
        reserva = self.client.session.get("solicitud_reserva", {})
        self.assertEqual(reserva.get("motivo"), "Grabación de cápsula educativa")
        self.assertEqual(reserva.get("area_id"), self.area.id)

    def test_paso3_revision_y_confirmacion_final(self):
        session = self.client.session
        session["solicitud_reserva"] = {
            "fecha": "2026-09-20",
            "bloques_ids": [self.bloque.id],
            "bloques_texto": "10:00 - 11:00",
            "area_id": self.area.id,
            "area_nombre": "Informática",
            "motivo": "Grabación de cápsula educativa",
            "observaciones": "Micrófono corbatero",
            "personas": 1,
            "acompanantes": [],
        }
        session.save()

        url = reverse("solicitar")
        # GET paso 3
        response = self.client.get(f"{url}?paso=3")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paso 3: Revisión y confirmación")
        self.assertContains(response, "Grabación de cápsula educativa")
        self.assertContains(response, "Informática")
        self.assertContains(response, "10:00 - 11:00")

        # POST paso 3 sin aceptar terminos -> error
        response = self.client.post(f"{url}?paso=3", {"paso": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tienes que aceptar los términos y condiciones")

        # POST paso 3 aceptando terminos -> exito
        response = self.client.post(f"{url}?paso=3", {"paso": "3", "acepta_terminos": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/enviada.html")
        self.assertContains(response, "Solicitud completa")
        self.assertContains(response, "10:00 - 11:00")
        self.assertContains(response, "Informática")
        # La sesion debe haberse limpiado
        self.assertNotIn("solicitud_reserva", self.client.session)

    def test_salto_a_paso_invalido_redirige_a_paso1(self):
        url = reverse("solicitar")
        # Intentar acceder a paso 3 sin sesion
        response = self.client.get(f"{url}?paso=3")
        self.assertEqual(response.status_code, 200)
        # Redirige internamente a paso 1
        self.assertContains(response, "Paso 1: Selecciona fecha y horario")
