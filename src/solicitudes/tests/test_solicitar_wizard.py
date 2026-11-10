from datetime import date, time, timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque, Bloqueo, Dia, Motivo, primera_fecha_pedible
from personas.models import Area, Rol
from solicitudes.models import Solicitud, SolicitudBloque
from solicitudes.services import guardar_solicitud_completa, motivo_horario_invalido

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
            "bloques_texto": f"{self.bloque.inicio:%H:%M} - {self.bloque.termino:%H:%M}"
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


class HorarioInvalidoEnElAsistenteTestCase(TestCase):
    """El horario elegido en el paso 1 vive en la sesión, y mientras se completan
    los pasos 2 y 3 la jornada, los bloqueos o las aprobaciones pueden cambiar."""

    MOTIVO = "Grabación cápsula docente"

    def setUp(self):
        self.area = Area.objects.create(nombre="Informática", activa=True)
        self.usuario = Usuario.objects.create_user(
            email="docente_asistente@uach.cl",
            first_name="María",
            last_name="Docente",
            password="testpassword123",
        )
        self.usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.usuario.areas.add(self.area)
        self.client.force_login(self.usuario)

        self.otro = Usuario.objects.create_user(
            email="rival_asistente@uach.cl",
            first_name="Rosa",
            last_name="Rival",
            password="testpassword123",
        )

        self.bloque, self.siguiente = Bloque.objects.filter(dia=Dia.JUEVES, activo=True)[:2]
        fecha_minima = primera_fecha_pedible()
        self.fecha = fecha_minima + date.resolution * ((Dia.JUEVES - fecha_minima.weekday()) % 7)
        # El texto se toma ahora: en la sesión queda el horario que se eligió,
        # aunque después cambie.
        self.textos = {
            b.id: f"{b.inicio:%H:%M} - {b.termino:%H:%M}" for b in (self.bloque, self.siguiente)
        }

    def _datos_reserva(self, bloques=None):
        bloques = bloques or [self.bloque]
        return {
            "area_id": self.area.id,
            "area_nombre": self.area.nombre,
            "fecha": self.fecha.isoformat(),
            "bloques_ids": [b.id for b in bloques],
            "bloques_texto": ", ".join(self.textos[b.id] for b in bloques),
            "motivo": self.MOTIVO,
            "observaciones": "",
            "personas": 1,
            "acompanantes": [],
        }

    def _cargar_sesion(self, bloques=None):
        session = self.client.session
        session["solicitud_reserva"] = self._datos_reserva(bloques)
        session.save()

    def _solicitud_con(self, bloque, solicitante=None, fecha=None, **estados):
        solicitud = Solicitud.objects.create(
            solicitante=solicitante or self.otro,
            area=self.area,
            fecha=fecha or self.fecha,
            motivo="Otra solicitud",
            **estados,
        )
        SolicitudBloque.objects.create(solicitud=solicitud, bloque=bloque)
        return solicitud

    def _reservar(self, bloque, **kwargs):
        return self._solicitud_con(bloque, estado_validacion=Solicitud.EstadoValidacion.ACEPTADA, **kwargs)

    def _bloquear(self, bloque, fecha=None):
        fecha = fecha or self.fecha
        return Bloqueo.objects.create(
            desde=fecha, hasta=fecha, bloque=bloque, motivo=Motivo.MANTENCION, detalle="Cambio de focos"
        )

    def _quitar(self, bloque):
        bloque.activo = False
        bloque.save(update_fields=["activo"])

    def _pedir_paso(self, metodo, paso):
        url = f"{reverse('solicitar')}?paso={paso}"
        if metodo == "GET":
            return self.client.get(url)
        if paso == 2:
            return self.client.post(url, {
                "paso": "datos",
                "motivo": self.MOTIVO,
                "personas": 1,
                "form-TOTAL_FORMS": "4",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "4",
            })
        return self.client.post(url, {"paso": "confirmacion", "acepta_terminos": "on"})

    def _assert_vuelve_al_paso_1(self, respuesta, mensaje):
        self.assertEqual(respuesta.status_code, 302)
        destino = urlparse(respuesta["Location"])
        self.assertEqual(destino.path, reverse("solicitar"))
        self.assertEqual(parse_qs(destino.query).get("fecha"), [self.fecha.isoformat()])

        # Se borra el horario y se conserva lo que ya se escribió.
        reserva = self.client.session["solicitud_reserva"]
        self.assertNotIn("fecha", reserva)
        self.assertNotIn("bloques_ids", reserva)
        self.assertEqual(reserva["motivo"], self.MOTIVO)

        self.assertFalse(Solicitud.objects.filter(motivo=self.MOTIVO).exists())

        pagina = self.client.get(respuesta["Location"])
        self.assertContains(pagina, "Paso 1: Selecciona fecha y horario")
        self.assertContains(pagina, f"Bloques para el día {self.fecha:%d/%m/%Y}")
        self.assertContains(pagina, mensaje)
        self.assertContains(pagina, "Elige otro horario")

    def _assert_rechaza_en_todo_el_asistente(self, mensaje, bloques=None):
        for metodo, paso in (("GET", 2), ("POST", 2), ("GET", 3), ("POST", 3)):
            with self.subTest(metodo=metodo, paso=paso):
                self._cargar_sesion(bloques)
                self._assert_vuelve_al_paso_1(self._pedir_paso(metodo, paso), mensaje)

        with self.subTest("guardar_solicitud_completa"):
            with self.assertRaises(ValidationError) as ctx:
                guardar_solicitud_completa(self.usuario, self._datos_reserva(bloques))
            self.assertIn(mensaje, " ".join(ctx.exception.messages))
            self.assertFalse(Solicitud.objects.filter(motivo=self.MOTIVO).exists())

    def test_bloque_quitado_de_la_jornada(self):
        self._quitar(self.bloque)
        self._assert_rechaza_en_todo_el_asistente(
            f"El bloque de las {self.bloque.inicio:%H:%M} ya no está en la jornada"
        )

    def test_hora_del_bloque_cambiada(self):
        # El id no cambia: sin esta validación, se guardaría un horario distinto
        # del que la persona vio y aceptó.
        self.bloque.inicio = time(self.bloque.inicio.hour, self.bloque.inicio.minute + 5)
        self.bloque.save(update_fields=["inicio"])
        self._assert_rechaza_en_todo_el_asistente("ya no coincide con la jornada actual")

    def test_bloque_bloqueado(self):
        self._bloquear(self.bloque)
        self._assert_rechaza_en_todo_el_asistente(
            f"La sala está bloqueada a las {self.bloque.inicio:%H:%M} (Mantención: Cambio de focos)"
        )

    def test_bloque_con_otra_solicitud_aprobada(self):
        self._reservar(self.bloque, solicitante=self.otro)
        self._assert_rechaza_en_todo_el_asistente(
            f"El bloque de las {self.bloque.inicio:%H:%M} ya está reservado"
        )

    def test_bloque_ya_pendiente_del_mismo_usuario(self):
        # Dos pestañas con el mismo bloque.
        self._solicitud_con(self.bloque, solicitante=self.usuario)
        self._assert_rechaza_en_todo_el_asistente(
            f"Ya tienes una solicitud pendiente para el bloque de las {self.bloque.inicio:%H:%M}"
        )

    def test_uno_de_dos_bloques_quitado_no_guarda_ninguno(self):
        self._quitar(self.siguiente)
        self._assert_rechaza_en_todo_el_asistente(
            f"El bloque de las {self.siguiente.inicio:%H:%M} ya no está en la jornada",
            bloques=[self.bloque, self.siguiente],
        )

    def test_uno_de_dos_bloques_reservado_no_guarda_ninguno(self):
        self._reservar(self.siguiente, solicitante=self.otro)
        self._assert_rechaza_en_todo_el_asistente(
            f"El bloque de las {self.siguiente.inicio:%H:%M} ya está reservado",
            bloques=[self.bloque, self.siguiente],
        )

    def test_el_aviso_no_revela_quien_tiene_la_reserva(self):
        self._reservar(self.bloque, solicitante=self.otro)
        self._cargar_sesion()
        respuesta = self._pedir_paso("POST", 3)
        pagina = self.client.get(respuesta["Location"])
        self.assertContains(pagina, "ya está reservado")
        self.assertNotContains(pagina, self.otro.email)
        self.assertNotContains(pagina, self.otro.last_name)

    def test_tras_volver_al_paso_1_puede_elegir_otro_y_conserva_lo_escrito(self):
        self._bloquear(self.bloque)
        self._cargar_sesion()
        self._pedir_paso("GET", 3)

        respuesta = self.client.post(reverse("solicitar"), {
            "paso": "horario",
            "fecha": self.fecha.isoformat(),
            "bloques": [str(self.siguiente.id)],
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("paso=2", respuesta["Location"])
        self.assertContains(self.client.get(respuesta["Location"]), self.MOTIVO)

        respuesta = self._pedir_paso("POST", 3)
        solicitud = Solicitud.objects.get(motivo=self.MOTIVO)
        self.assertRedirects(respuesta, reverse("solicitud_enviada", args=[solicitud.id]))
        self.assertEqual(list(solicitud.bloques.all()), [self.siguiente])

    def test_lo_que_ocurre_en_otro_bloque_u_otra_fecha_no_interfiere(self):
        otra_fecha = self.fecha + timedelta(days=7)
        self._bloquear(self.siguiente)
        self._bloquear(self.bloque, fecha=otra_fecha)
        # Cada una en su fecha: un bloque bloqueado ya no se puede reservar (impedimento).
        self._reservar(self.bloque, solicitante=self.otro, fecha=otra_fecha + timedelta(days=14))
        self._solicitud_con(self.bloque, solicitante=self.usuario, fecha=otra_fecha + timedelta(days=7))

        self._cargar_sesion()
        for paso in (2, 3):
            self.assertEqual(self._pedir_paso("GET", paso).status_code, 200)
        respuesta = self._pedir_paso("POST", 3)
        solicitud = Solicitud.objects.get(motivo=self.MOTIVO)
        self.assertRedirects(respuesta, reverse("solicitud_enviada", args=[solicitud.id]))

    def test_un_bloqueo_levantado_no_interfiere(self):
        bloqueo = self._bloquear(self.bloque)
        bloqueo.levantado_en = bloqueo.bloqueado_en
        bloqueo.save(update_fields=["levantado_en"])
        self.assertIsNone(self._motivo())

    def test_una_solicitud_pendiente_de_otra_persona_no_interfiere(self):
        self._solicitud_con(self.bloque, solicitante=self.otro)
        self.assertIsNone(self._motivo())

    def test_solicitudes_que_ya_no_ocupan_el_bloque_no_cuentan(self):
        rechazada = {"estado_validacion": Solicitud.EstadoValidacion.RECHAZADA}
        retirada = {"estado_validacion": Solicitud.EstadoValidacion.RETIRADA}
        cancelada = {
            "estado_validacion": Solicitud.EstadoValidacion.ACEPTADA,
            "estado_confirmacion": Solicitud.EstadoConfirmacion.CANCELADA,
        }
        casos = (
            ("rechazada de otra persona", self.otro, rechazada),
            ("retirada de otra persona", self.otro, retirada),
            ("cancelada de otra persona", self.otro, cancelada),
            ("rechazada propia", self.usuario, rechazada),
            ("retirada propia", self.usuario, retirada),
            ("cancelada propia", self.usuario, cancelada),
        )
        for nombre, solicitante, estados in casos:
            with self.subTest(nombre):
                solicitud = self._solicitud_con(self.bloque, solicitante=solicitante, **estados)
                self.assertIsNone(self._motivo())
                solicitud.delete()

    def _motivo(self):
        datos = self._datos_reserva()
        return motivo_horario_invalido(self.usuario, self.fecha, datos["bloques_ids"], datos["bloques_texto"])

    def test_los_mensajes_de_respaldo_no_muestran_ids_ni_fechas_iso(self):
        # Solo se ven si una aprobación llega justo entre la validación y el
        # guardado, o desde /admin/. El solicitante no conoce el id del bloque.
        casos = (
            ("reservado", {"estado_validacion": Solicitud.EstadoValidacion.ACEPTADA}, self.otro),
            ("pendiente propia", {}, self.usuario),
        )
        for nombre, estados, solicitante in casos:
            with self.subTest(nombre):
                previa = self._solicitud_con(self.bloque, solicitante=solicitante, **estados)
                nueva = Solicitud.objects.create(
                    solicitante=self.usuario, area=self.area, fecha=self.fecha, motivo="Segunda"
                )
                with self.assertRaises(ValidationError) as ctx:
                    SolicitudBloque.objects.create(solicitud=nueva, bloque=self.bloque)
                mensaje = " ".join(ctx.exception.messages)
                self.assertNotIn(f"#{self.bloque.id}", mensaje)
                self.assertNotIn(self.fecha.isoformat(), mensaje)
                self.assertIn(f"{self.bloque.inicio:%H:%M}", mensaje)
                nueva.delete()
                previa.delete()


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