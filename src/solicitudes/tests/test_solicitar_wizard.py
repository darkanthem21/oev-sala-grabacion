from datetime import date
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque, Dia, primera_fecha_pedible
from personas.models import Area, Rol
from solicitudes.models import Solicitud, SolicitudBloque

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

    def test_ac1_001_omision_seleccion_area(self):
        '''
        Caso de Prueba [AC1-001]: Omisión de selección de área para usuarios con área única
        '''
        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/solicitar.html")
        self.assertContains(response, "Paso 1: Selecciona fecha y horario")
        self.assertNotContains(response, "Cambiar área")
        self.assertEqual(self.client.session.get("solicitud_reserva", {}).get("area_id"), self.area.id)

    def test_ac4_001_seleccion_obligatoria_area(self):
        '''
        Caso de Prueba [AC4-001]: Selección obligatoria de área para usuarios con múltiples áreas
        '''
        area2 = Area.objects.create(nombre="Medicina", activa=True)
        self.usuario.areas.add(area2)

        # Intento de acceso directo, debe redirigir a selección
        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("solicitar_area"), response["Location"])

        # Pantalla de selección y POST válido
        url_area = reverse("solicitar_area")
        response_area = self.client.get(url_area)
        self.assertContains(response_area, "Informática")
        self.assertContains(response_area, "Medicina")

        response_post = self.client.post(url_area, {"area": str(area2.id)})
        self.assertEqual(response_post.status_code, 302)
        self.assertIn(reverse("solicitar"), response_post["Location"])
        self.assertEqual(self.client.session.get("solicitud_reserva", {}).get("area_id"), area2.id)

    def test_ac3_001_flujo_principal_solicitud(self):
        '''
        Caso de Prueba [AC3-001]: Flujo principal de solicitud exitosa (Ruta Feliz)
        '''
        url = reverse("solicitar")
        
        # Paso 1: Seleccionar Horario
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

        # Paso 3: Confirmación y aceptación de T&C
        response_p3 = self.client.post(f"{url}?paso=3", {
            "paso": "confirmacion",
            "acepta_terminos": "on",
        })
        
        solicitud = Solicitud.objects.get(solicitante=self.usuario)
        self.assertRedirects(response_p3, reverse("solicitud_enviada", args=[solicitud.id]))
        self.assertEqual(solicitud.motivo, "Grabación cápsula docente")
        self.assertEqual(solicitud.estado_validacion, Solicitud.EstadoValidacion.PENDIENTE)
        self.assertEqual(solicitud.acompanantes.count(), 1)

    def test_ac6_001_validacion_cantidad_duplicidad_acompanantes(self):
        '''
        Caso de Prueba [AC6-001]: Validación de cantidad y duplicidad de acompañantes
        '''
        # Pre-cargar paso 1 en la sesión
        session = self.client.session
        session["solicitud_reserva"] = {
            "area_id": self.area.id,
            "area_nombre": "Informática",
            "fecha": self.fecha_prueba.isoformat(),
            "bloques_ids": [self.bloque.id],
            "bloques_texto": f"{self.bloque.inicio:%H:%M} – {self.bloque.termino:%H:%M}"
        }
        session.save()

        url = f"{reverse('solicitar')}?paso=2"

        # Caso A: Declaradas 2 personas pero se llenan 3
        response_a = self.client.post(url, {
            "paso": "datos",
            "motivo": "Grabación",
            "personas": 2,
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "4",
            "form-0-nombre": "Acomp 1", "form-0-correo": "a1@uach.cl",
            "form-1-nombre": "Acomp 2", "form-1-correo": "a2@uach.cl",
            "form-2-nombre": "", "form-2-correo": "",
            "form-3-nombre": "", "form-3-correo": "",
        })
        self.assertContains(response_a, "faltan los datos de 1 acompañante(s); tienes 2 completo(s)")

        # Caso B: Correo duplicado
        response_b = self.client.post(url, {
            "paso": "datos",
            "motivo": "Grabación",
            "personas": 3,
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "4",
            "form-0-nombre": "Acomp 1", "form-0-correo": "dup@uach.cl",
            "form-1-nombre": "Acomp 2", "form-1-correo": "dup@uach.cl",
            "form-2-nombre": "", "form-2-correo": "",
            "form-3-nombre": "", "form-3-correo": "",
        })
        self.assertContains(response_b, "Hay un correo repetido entre los acompañantes")

        # Caso C: Correo del propio solicitante
        response_c = self.client.post(url, {
            "paso": "datos",
            "motivo": "Grabación",
            "personas": 2,
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "4",
            "form-0-nombre": "Acomp 1", "form-0-correo": "docente@uach.cl",
            "form-1-nombre": "", "form-1-correo": "",
            "form-2-nombre": "", "form-2-correo": "",
            "form-3-nombre": "", "form-3-correo": "",
        })
        self.assertContains(response_c, "Tu propio correo ya está incluido")

    def test_ac10_001_obligatoriedad_terminos_condiciones(self):
        '''
        Caso de Prueba [AC10-001]: Obligatoriedad de aceptación de Términos y Condiciones
        '''
        session = self.client.session
        session["solicitud_reserva"] = {
            "area_id": self.area.id,
            "fecha": self.fecha_prueba.isoformat(),
            "bloques_ids": [self.bloque.id],
            "motivo": "Prueba términos",
            "personas": 1,
            "acompanantes": []
        }
        session.save()

        url = f"{reverse('solicitar')}?paso=3"
        response = self.client.post(url, {
            "paso": "confirmacion"
            # Omitimos explícitamente "acepta_terminos"
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tienes que aceptar los términos y condiciones")
        self.assertEqual(Solicitud.objects.count(), 0)

    def test_ac8_001_solicitud_rango_fechas(self):
        '''
        Caso de Prueba [AC8-001]: Solicitud de bloque en un rango de fechas (Bloques Recurrentes)
        Actualmente el modelo solo soporta 1 fecha/solicitud. La prueba valida que se rechace un string no-ISO.
        '''
        url = reverse("solicitar")
        response_p1 = self.client.post(url, {
            "paso": "horario",
            "fecha": "2026-10-10 to 2026-10-15",
            "bloques": [str(self.bloque.id)],
        })
        self.assertEqual(response_p1.status_code, 200)
        self.assertContains(response_p1, "Por favor, selecciona un d")

    def test_techo_en_solicitar(self):
        url = reverse("solicitar")
        response = self.client.get(url)
        self.assertContains(response, 'class="techo"')
        self.assertContains(response, 'Cerrar sesión')

    def test_techo_en_sin_area(self):
        usuario_sin_area = Usuario.objects.create_user(
            email="sinarea@uach.cl", password="testpassword123"
        )
        usuario_sin_area.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.client.force_login(usuario_sin_area)
        
        response = self.client.get(reverse("solicitar"))
        self.assertTemplateUsed(response, "solicitudes/sin_area.html")
        self.assertContains(response, 'class="techo"')


class DisponibilidadEfectivaTestCase(TestCase):
    # (El contenido original íntegro de DisponibilidadEfectivaTestCase se mantiene aquí)
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


class SolicitudEnviadaTestCase(TestCase):
    # (El contenido original íntegro de SolicitudEnviadaTestCase se mantiene aquí)
    def setUp(self):
        self.area = Area.objects.create(nombre="Informática", activa=True)
        self.usuario = Usuario.objects.create_user(email="docente@uach.cl", password="x")
        self.usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.client.force_login(self.usuario)
        fecha_minima = primera_fecha_pedible()
        self.fecha = fecha_minima + date.resolution * ((Dia.JUEVES - fecha_minima.weekday()) % 7)

    def _solicitud(self, usuario, **estados):
        return Solicitud.objects.create(solicitante=usuario, area=self.area, fecha=self.fecha, motivo="Grabar", **estados)

    def test_no_muestra_solicitudes_ajenas(self):
        otro = Usuario.objects.create_user(email="otro@uach.cl", password="x")
        ajena = self._solicitud(otro)
        response = self.client.get(reverse("solicitud_enviada", args=[ajena.id]))
        self.assertEqual(response.status_code, 404)

    def test_requiere_ingreso_de_solicitante(self):
        propia = self._solicitud(self.usuario)
        self.client.logout()
        response = self.client.get(reverse("solicitud_enviada", args=[propia.id]))
        self.assertIn(reverse("login_solicitante"), response["Location"])

    def test_muestra_el_estado_actual(self):
        en_revision = self._solicitud(self.usuario)
        self.assertContains(self.client.get(reverse("solicitud_enviada", args=[en_revision.id])), "se encuentra en revisión")
        aceptada = self._solicitud(self.usuario, estado_validacion=Solicitud.EstadoValidacion.ACEPTADA)
        response = self.client.get(reverse("solicitud_enviada", args=[aceptada.id]))
        self.assertContains(response, "está aceptada")
        self.assertNotContains(response, "se encuentra en revisión")