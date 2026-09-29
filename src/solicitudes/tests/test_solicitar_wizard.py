from datetime import date, time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque
from personas.models import Area
from solicitudes.models import Acompanante, Solicitud, SolicitudBloque
from solicitudes.wizard import PasoSolicitud, SolicitudWizard, obtener_limites_reserva

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

    def test_paso1_post_fecha_fuera_de_rango_muestra_error(self):
        url = reverse("solicitar")
        response = self.client.post(f"{url}?paso=1", {
            "paso": "1",
            "fecha": "2027-05-10",
            "bloques": [str(self.bloque.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La fecha seleccionada no está dentro del período permitido para reservas.")

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

        # Debe haberse guardado en la base de datos
        self.assertEqual(Solicitud.objects.count(), 1)
        solicitud = Solicitud.objects.first()
        self.assertEqual(solicitud.solicitante, self.usuario)
        self.assertEqual(solicitud.area, self.area)
        self.assertEqual(solicitud.motivo, "Grabación de cápsula educativa")
        self.assertEqual(solicitud.estado_validacion, Solicitud.EstadoValidacion.PENDIENTE)
        self.assertEqual(solicitud.estado_confirmacion, Solicitud.EstadoConfirmacion.NO_HABILITADA)
        self.assertEqual(solicitud.total_personas, 1)
        self.assertEqual(solicitud.bloques.count(), 1)
        self.assertEqual(solicitud.bloques.first(), self.bloque)

    def test_paso3_con_acompanantes_guarda_acompanantes_y_bloques(self):
        session = self.client.session
        session["solicitud_reserva"] = {
            "fecha": "2026-09-20",
            "bloques_ids": [self.bloque.id],
            "bloques_texto": "10:00 - 11:00",
            "area_id": self.area.id,
            "area_nombre": "Informática",
            "motivo": "Cápsula con invitados",
            "personas": 3,
            "acompanantes": [
                {"nombre": "Acompañante Uno", "correo": "uno@uach.cl"},
                {"nombre": "Acompañante Dos", "correo": "dos@uach.cl"},
            ],
        }
        session.save()

        url = reverse("solicitar")
        response = self.client.post(f"{url}?paso=3", {"paso": "3", "acepta_terminos": "1"})
        self.assertEqual(response.status_code, 200)

        solicitud = Solicitud.objects.get(motivo="Cápsula con invitados")
        self.assertEqual(solicitud.total_personas, 3)
        self.assertEqual(solicitud.acompanantes.count(), 2)
        self.assertTrue(solicitud.acompanantes.filter(correo="uno@uach.cl").exists())
        self.assertTrue(solicitud.acompanantes.filter(correo="dos@uach.cl").exists())

    def test_salto_a_paso_invalido_redirige_a_paso1(self):
        url = reverse("solicitar")
        # Intentar acceder a paso 3 sin sesion
        response = self.client.get(f"{url}?paso=3")
        self.assertEqual(response.status_code, 200)
        # Redirige internamente a paso 1
        self.assertContains(response, "Paso 1: Selecciona fecha y horario")


class WizardClasesTestCase(TestCase):
    def test_paso_solicitud_resolver(self):
        self.assertEqual(PasoSolicitud.resolver(1), PasoSolicitud.HORARIO)
        self.assertEqual(PasoSolicitud.resolver("2"), PasoSolicitud.DATOS)
        self.assertEqual(PasoSolicitud.resolver(3), PasoSolicitud.CONFIRMACION)
        self.assertEqual(PasoSolicitud.resolver("invalido"), PasoSolicitud.HORARIO)
        self.assertEqual(PasoSolicitud.resolver(99), PasoSolicitud.HORARIO)
        self.assertEqual(PasoSolicitud.resolver(None), PasoSolicitud.HORARIO)

    def test_paso_solicitud_validar_acceso(self):
        # Sesión vacía solo permite paso 1
        self.assertEqual(PasoSolicitud.HORARIO.validar_acceso({}), PasoSolicitud.HORARIO)
        self.assertEqual(PasoSolicitud.DATOS.validar_acceso({}), PasoSolicitud.HORARIO)
        self.assertEqual(PasoSolicitud.CONFIRMACION.validar_acceso({}), PasoSolicitud.HORARIO)

        # Con datos de paso 1, permite paso 1 y 2, pero no 3
        sesion_paso1 = {"fecha": "2026-09-20", "bloques_ids": [1]}
        self.assertEqual(PasoSolicitud.HORARIO.validar_acceso(sesion_paso1), PasoSolicitud.HORARIO)
        self.assertEqual(PasoSolicitud.DATOS.validar_acceso(sesion_paso1), PasoSolicitud.DATOS)
        self.assertEqual(PasoSolicitud.CONFIRMACION.validar_acceso(sesion_paso1), PasoSolicitud.DATOS)

        # Con datos de paso 1 y 2, permite paso 3
        sesion_paso2 = {
            "fecha": "2026-09-20",
            "bloques_ids": [1],
            "area_id": 1,
            "motivo": "Grabación",
        }
        self.assertEqual(PasoSolicitud.CONFIRMACION.validar_acceso(sesion_paso2), PasoSolicitud.CONFIRMACION)

    def test_solicitud_wizard_operaciones_sesion(self):
        session_mock = {}
        wizard = SolicitudWizard(session_mock)

        # Inicialmente vacío
        self.assertEqual(wizard.datos, {})

        # Guardar horario
        wizard.guardar_horario("2026-09-20", [1, 2], "10:00 - 12:00")
        self.assertEqual(wizard.datos["fecha"], "2026-09-20")
        self.assertEqual(wizard.datos["bloques_ids"], [1, 2])
        self.assertEqual(wizard.datos["bloques_texto"], "10:00 - 12:00")

        # Guardar datos actividad
        wizard.guardar_datos_actividad(
            area_id=5,
            area_nombre="Medicina",
            motivo="Simulación clínica",
            observaciones="Cámara cenital",
            personas=2,
            acompanantes=[{"nombre": "Juan Pérez", "correo": "juan@uach.cl"}],
        )
        self.assertEqual(wizard.datos["area_id"], 5)
        self.assertEqual(wizard.datos["motivo"], "Simulación clínica")

        # Obtener resumen estructurado
        resumen = wizard.obtener_resumen()
        self.assertEqual(resumen["fecha"], date(2026, 9, 20))
        self.assertEqual(resumen["fecha_str"], "2026-09-20")
        self.assertEqual(resumen["area_nombre"], "Medicina")
        self.assertEqual(resumen["personas"], 2)
        self.assertEqual(len(resumen["acompanantes"]), 1)

        # Limpiar sesión
        wizard.limpiar()
        self.assertEqual(wizard.datos, {})
        self.assertNotIn(SolicitudWizard.CLAVE_SESION, session_mock)

    def test_obtener_limites_reserva(self):
        # Por defecto 4 meses de anticipación
        f_min, f_max = obtener_limites_reserva(date(2026, 9, 28))
        self.assertEqual(f_min, date(2026, 9, 1))
        self.assertEqual(f_max, date(2027, 1, 31))

        # Configuración personalizada de anticipación
        with self.settings(MESES_ANTICIPACION_MAXIMA=2):
            f_min, f_max = obtener_limites_reserva(date(2026, 9, 28))
            self.assertEqual(f_min, date(2026, 9, 1))
            self.assertEqual(f_max, date(2026, 11, 30))

        # 0 meses (solo mes en curso)
        with self.settings(MESES_ANTICIPACION_MAXIMA=0):
            f_min, f_max = obtener_limites_reserva(date(2026, 9, 28))
            self.assertEqual(f_min, date(2026, 9, 1))
            self.assertEqual(f_max, date(2026, 9, 30))

    def test_barra_superior_en_solicitar(self):
        area = Area.objects.create(nombre="Test Area Barra", activa=True)
        usuario = Usuario.objects.create_user(
            email="barra_solicitar@uach.cl",
            first_name="Docente",
            last_name="Barra",
            password="testpassword123",
        )
        usuario.areas.add(area)
        self.client.force_login(usuario)

        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="barra-superior"')
        self.assertContains(response, 'Facultad-color-negro.png')
        self.assertContains(response, usuario.email)
        self.assertContains(response, 'action="/logout/"')
        self.assertContains(response, 'Cerrar sesión')

    def test_barra_superior_en_sin_area(self):
        usuario_sin_area = Usuario.objects.create_user(
            email="sinarea@uach.cl",
            first_name="Sin",
            last_name="Area",
            password="testpassword123",
        )
        self.client.force_login(usuario_sin_area)
        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/sin_area.html")
        self.assertContains(response, 'class="barra-superior"')
        self.assertContains(response, 'Facultad-color-negro.png')
        self.assertContains(response, "sinarea@uach.cl")
        self.assertContains(response, 'action="/logout/"')


