from datetime import date, datetime, time
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque, Dia, primera_fecha_pedible
from personas.models import Area, Rol
from solicitudes.models import Acompanante, Solicitud, SolicitudBloque
from solicitudes.services import guardar_solicitud_completa
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
        self.usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.usuario.areas.add(self.area)
        self.client.force_login(self.usuario)

        self.bloque = Bloque.objects.filter(dia=Dia.JUEVES, activo=True).first()
        fecha_minima = primera_fecha_pedible()
        self.fecha_prueba = fecha_minima + date.resolution * ((Dia.JUEVES - fecha_minima.weekday()) % 7)

    def test_usuario_una_sola_area_autoselecciona_y_va_a_paso1_calendario(self):
        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/solicitar.html")
        self.assertContains(response, "Paso 1: Selecciona fecha y horario")
        self.assertContains(response, "Horario y disponibilidad")
        self.assertContains(response, "Paso 1 de 3")
        self.assertNotContains(response, "Cambiar área")
        self.assertEqual(self.client.session.get("solicitud_reserva", {}).get("area_id"), self.area.id)
        self.assertContains(response, f'hx-get="/solicitar/bloques/?fecha={self.fecha_prueba.isoformat()}"')
        self.assertContains(response, 'hx-push-url="false"')

    def test_usuario_con_multiples_areas_redirige_a_solicitar_area(self):
        area2 = Area.objects.create(nombre="Medicina", activa=True)
        self.usuario.areas.add(area2)

        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("solicitar_area"), response["Location"])

    def test_pantalla_solicitar_area_muestra_listado_y_procesa_seleccion(self):
        area2 = Area.objects.create(nombre="Medicina", activa=True)
        self.usuario.areas.add(area2)

        url_area = reverse("solicitar_area")
        response = self.client.get(url_area)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/seleccionar_area.html")
        self.assertContains(response, "Informática")
        self.assertContains(response, "Medicina")

        response_post = self.client.post(url_area, {"area": str(area2.id)})
        self.assertEqual(response_post.status_code, 302)
        self.assertIn(reverse("solicitar"), response_post["Location"])
        self.assertEqual(self.client.session.get("solicitud_reserva", {}).get("area_id"), area2.id)

    def test_flujo_completo_tres_pasos(self):
        # Paso 1: Seleccionar Horario
        url = reverse("solicitar")
        response_p1 = self.client.post(url, {
            "paso": "horario",
            "fecha": self.fecha_prueba.isoformat(),
            "bloques": [str(self.bloque.id)],
        })
        self.assertEqual(response_p1.status_code, 302)
        self.assertIn("paso=2", response_p1["Location"])

        # Paso 2: Datos de la actividad
        response_p2 = self.client.post(f"{url}?paso=2", {
            "paso": "datos",
            "motivo": "Grabación cápsula docente",
            "observaciones": "Requiere proyector",
            "personas": 2,
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "4",
            "form-0-nombre": "Juan Acompañante",
            "form-0-correo": "juan@uach.cl",
            "form-1-nombre": "",
            "form-1-correo": "",
            "form-2-nombre": "",
            "form-2-correo": "",
            "form-3-nombre": "",
            "form-3-correo": "",
        })
        self.assertEqual(response_p2.status_code, 302)
        self.assertIn("paso=3", response_p2["Location"])

        # Paso 3: Confirmación
        response_p3 = self.client.post(f"{url}?paso=3", {
            "paso": "confirmacion",
            "acepta_terminos": "on",
        })
        self.assertEqual(response_p3.status_code, 200)
        self.assertTemplateUsed(response_p3, "solicitudes/enviada.html")
        self.assertContains(response_p3, "Solicitud completa")
        self.assertContains(response_p3, "Grabación cápsula docente")

        # Verificar persistencia en base de datos
        solicitud = Solicitud.objects.filter(solicitante=self.usuario).first()
        self.assertIsNotNone(solicitud)
        self.assertEqual(solicitud.motivo, "Grabación cápsula docente")
        self.assertEqual(solicitud.area, self.area)
        self.assertEqual(solicitud.personas, 2)
        self.assertEqual(solicitud.solicitudes_bloques.count(), 1)
        self.assertEqual(solicitud.solicitudes_bloques.first().bloque, self.bloque)
        self.assertEqual(solicitud.fecha, self.fecha_prueba)
        self.assertEqual(solicitud.acompanantes.count(), 1)
        self.assertEqual(solicitud.acompanantes.first().nombre, "Juan Acompañante")

    def test_techo_en_solicitar(self):
        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="techo"')
        self.assertContains(response, 'Facultad-color-negro.png')
        self.assertContains(response, self.usuario.get_full_name())
        self.assertContains(response, 'action="/logout/"')
        self.assertContains(response, 'Cerrar sesión')

    def test_techo_en_sin_area(self):
        usuario_sin_area = Usuario.objects.create_user(
            email="sinarea@uach.cl",
            first_name="Sin",
            last_name="Area",
            password="testpassword123",
        )
        usuario_sin_area.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.client.force_login(usuario_sin_area)
        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/sin_area.html")
        self.assertContains(response, 'class="techo"')
        self.assertContains(response, 'Facultad-color-negro.png')
        self.assertContains(response, "Sin Area")
        self.assertContains(response, 'action="/logout/"')


class DisponibilidadEfectivaTestCase(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Informática", activa=True)
        self.usuario = Usuario.objects.create_user(
            email="docente_disp@uach.cl",
            first_name="María",
            last_name="Docente",
            password="testpassword123",
        )
        self.usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.usuario.areas.add(self.area)
        self.client.force_login(self.usuario)

        self.bloque = Bloque.objects.filter(dia=Dia.JUEVES, activo=True).first()
        fecha_minima = primera_fecha_pedible()
        self.fecha_prueba = fecha_minima + date.resolution * ((Dia.JUEVES - fecha_minima.weekday()) % 7)

    def test_wizard_paso1_rechaza_bloque_con_solicitud_aceptada(self):
        otro_usuario = get_user_model().objects.create_user(email="otro_disp@uach.cl", password="123")
        otro_usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        sol_aceptada = Solicitud.objects.create(
            solicitante=otro_usuario,
            area=self.area,
            fecha=self.fecha_prueba,
            motivo="Reserva aceptada previa",
            estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
            estado_confirmacion=Solicitud.EstadoConfirmacion.CONFIRMADA,
        )
        SolicitudBloque.objects.create(solicitud=sol_aceptada, bloque=self.bloque)

        url = reverse("solicitar")
        response = self.client.post(url, {
            "paso": "horario",
            "fecha": self.fecha_prueba.isoformat(),
            "bloques": [str(self.bloque.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Uno o más de los bloques seleccionados ya no están disponibles")

    def test_modelo_solicitud_bloque_rechaza_bloque_con_solicitud_aceptada(self):
        sol_aceptada = Solicitud.objects.create(
            solicitante=self.usuario,
            area=self.area,
            fecha=self.fecha_prueba,
            motivo="Reserva aceptada previa",
            estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
            estado_confirmacion=Solicitud.EstadoConfirmacion.CONFIRMADA,
        )
        SolicitudBloque.objects.create(solicitud=sol_aceptada, bloque=self.bloque)

        otra_solicitud = Solicitud.objects.create(
            solicitante=self.usuario,
            area=self.area,
            fecha=self.fecha_prueba,
            motivo="Segunda solicitud",
        )
        with self.assertRaises(ValidationError) as ctx:
            SolicitudBloque.objects.create(
                solicitud=otra_solicitud,
                bloque=self.bloque,
            )
        self.assertIn("ya se encuentra reservado", str(ctx.exception).lower())

    def test_modelo_solicitud_bloque_rechaza_bloque_con_solicitud_propia_pendiente(self):
        sol_pendiente = Solicitud.objects.create(
            solicitante=self.usuario,
            area=self.area,
            fecha=self.fecha_prueba,
            motivo="Primera solicitud pendiente",
            estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
        )
        SolicitudBloque.objects.create(solicitud=sol_pendiente, bloque=self.bloque)

        otra_solicitud = Solicitud.objects.create(
            solicitante=self.usuario,
            area=self.area,
            fecha=self.fecha_prueba,
            motivo="Segunda solicitud duplicada",
            estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
        )
        with self.assertRaises(ValidationError) as ctx:
            SolicitudBloque.objects.create(
                solicitud=otra_solicitud,
                bloque=self.bloque,
            )
        self.assertIn("ya tienes una solicitud pendiente", str(ctx.exception).lower())

    def test_modelo_solicitud_bloque_permite_solicitud_pendiente_de_distinto_usuario(self):
        sol_pendiente = Solicitud.objects.create(
            solicitante=self.usuario,
            area=self.area,
            fecha=self.fecha_prueba,
            motivo="Primera solicitud pendiente",
            estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
        )
        SolicitudBloque.objects.create(solicitud=sol_pendiente, bloque=self.bloque)

        otro_usuario = get_user_model().objects.create_user(email="competidor@uach.cl", password="123")
        otro_usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        otra_solicitud = Solicitud.objects.create(
            solicitante=otro_usuario,
            area=self.area,
            fecha=self.fecha_prueba,
            motivo="Solicitud de otro docente",
            estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
        )
        sb = SolicitudBloque.objects.create(
            solicitud=otra_solicitud,
            bloque=self.bloque,
        )
        self.assertIsNotNone(sb.pk)
