import json
from datetime import date, time
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from agenda.models import Bloque
from personas.models import Area, Rol, Usuario
from solicitudes.models import Solicitud, SolicitudBloque
from uso.checkout.models import Checkout, FotoIntegridad, FormularioCheckout


class CheckoutTests(TestCase):
    def setUp(self):
        self.directorio = TemporaryDirectory()
        self.addCleanup(self.directorio.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.directorio.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.admin = Usuario.objects.create_user(email="admin@example.com", is_staff=True)
        self.apoyo = Usuario.objects.create_user(email="apoyo@example.com")
        self.apoyo.groups.add(Group.objects.get(name=Rol.APOYO))
        self.persona = Usuario.objects.create_user(email="persona@example.com")
        self.listado = FormularioCheckout.cargar()
        self.listado.secciones = [{"id": "sala", "titulo": "Integridad", "preguntas": [{"id": "pared", "texto": "¿La pared está sin daños?"}]}]
        self.listado.save()
        self.solicitud = Solicitud.objects.create(
            solicitante=self.persona, area=Area.objects.create(nombre="Pruebas"),
            fecha=date(2020, 1, 6), motivo="Grabación", estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
            estado_confirmacion=Solicitud.EstadoConfirmacion.CONFIRMADA,
        )
        bloque = Bloque.objects.create(dia=0, inicio=time(9), termino=time(10))
        self.ticket = SolicitudBloque.objects.create(solicitud=self.solicitud, bloque=bloque)
        self.url = reverse("checkout_apoyo", args=[self.ticket.ticket])
        self.editor = reverse("panel_checkout")
        self.client.force_login(self.apoyo)

    def datos(self, **cambios):
        return {"revision": self.listado.revision, "hora_salida": "10:00", "respuesta_pared": "si", **cambios}

    def foto(self):
        salida = BytesIO()
        Image.new("RGB", (4, 4), "white").save(salida, "PNG")
        return SimpleUploadedFile("evidencia.png", salida.getvalue(), content_type="image/png")

    def test_preguntas_obligatorias_en_servidor(self):
        datos = self.datos()
        del datos["respuesta_pared"]
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("respuesta_pared", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_no_sin_evidencia_bloquea_envio(self):
        respuesta = self.client.post(self.url, self.datos(respuesta_pared="no"))
        self.assertIn("observacion_pared", respuesta.context["form"].errors)
        self.assertIn("foto_pared", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_observacion_corta_no_es_suficiente(self):
        respuesta = self.client.post(self.url, self.datos(respuesta_pared="no", observacion_pared="daño", foto_pared=self.foto()))
        self.assertIn("observacion_pared", respuesta.context["form"].errors)
        self.assertFalse(FotoIntegridad.objects.exists())

    def test_archivo_falso_no_es_evidencia(self):
        archivo = SimpleUploadedFile("foto.png", b"no es imagen", content_type="image/png")
        respuesta = self.client.post(self.url, self.datos(respuesta_pared="no", observacion_pared="Hay un daño visible en la pared.", foto_pared=archivo))
        self.assertIn("foto_pared", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_no_con_evidencia_se_guarda_y_se_consulta(self):
        respuesta = self.client.post(self.url, self.datos(respuesta_pared="no", observacion_pared="Hay un daño visible en la pared.", foto_pared=self.foto()))
        self.assertEqual(respuesta.status_code, 302)
        registro = Checkout.objects.get()
        self.assertFalse(registro.respuestas["pared"]["cumple"])
        foto = registro.fotos.get()
        self.assertTrue(foto.archivo.storage.exists(foto.archivo.name))
        self.assertContains(self.client.get(self.url), "Descargar foto de integridad")

    def test_si_no_necesita_evidencia_ni_permite_duplicados(self):
        self.assertEqual(self.client.post(self.url, self.datos()).status_code, 302)
        self.assertEqual(self.client.post(self.url, self.datos()).status_code, 302)
        self.assertEqual(Checkout.objects.count(), 1)
        self.assertFalse(FotoIntegridad.objects.exists())

    def test_completado_visible_para_otro_apoyo(self):
        self.client.post(self.url, self.datos())
        otro = Usuario.objects.create_user(email="otro@example.com")
        otro.groups.add(Group.objects.get(name=Rol.APOYO))
        self.client.force_login(otro)
        self.assertContains(self.client.get(self.url), "Check-out completado")

    def test_cambio_de_listado_no_modifica_reporte(self):
        self.client.post(self.url, self.datos())
        self.listado.secciones[0]["preguntas"][0]["texto"] = "Pregunta nueva"
        self.listado.save()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "¿La pared está sin daños?")
        self.assertNotContains(respuesta, "Pregunta nueva")

    def test_revision_desactualizada_bloquea_envio(self):
        self.listado.revision += 1
        self.listado.save()
        respuesta = self.client.post(self.url, self.datos(revision=1))
        self.assertContains(respuesta, "El listado cambió")
        self.assertFalse(Checkout.objects.exists())

    def test_cancelado_o_futuro_no_admite_checkout(self):
        self.solicitud.estado_confirmacion = Solicitud.EstadoConfirmacion.CANCELADA
        self.solicitud.save()
        self.assertEqual(self.client.post(self.url, self.datos()).status_code, 404)
        self.solicitud.estado_confirmacion = Solicitud.EstadoConfirmacion.NO_HABILITADA
        self.solicitud.fecha = date(2099, 1, 5)
        self.solicitud.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_editor_solo_administracion(self):
        self.assertEqual(self.client.get(self.editor).status_code, 302)
        self.assertEqual(self.client.post(self.editor, {"secciones": "[]", "revision": 1}).status_code, 302)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.editor), "Publicar listado")

    def test_publicacion_de_secciones_y_preguntas(self):
        self.client.force_login(self.admin)
        secciones = [{"id": "nueva", "titulo": "Nueva sección", "preguntas": [{"id": "nuevo", "texto": "¿Todo correcto?"}]}]
        respuesta = self.client.post(self.editor, {"revision": 1, "secciones": json.dumps(secciones)})
        self.assertEqual(respuesta.status_code, 302)
        self.listado.refresh_from_db()
        self.assertEqual(self.listado.secciones, secciones)
        self.assertEqual(self.listado.revision, 2)
        self.assertEqual(self.listado.actualizado_por, self.admin)
        self.client.force_login(self.apoyo)
        respuesta = self.client.post(self.url, {"revision": 2, "hora_salida": "10:00", "respuesta_nuevo": "no"})
        self.assertIn("foto_nuevo", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_editor_rechaza_listado_vacio_y_ids_duplicados(self):
        self.client.force_login(self.admin)
        for secciones in ([], [{"id": "duplicado", "titulo": "Sección", "preguntas": [{"id": "duplicado", "texto": "Pregunta"}]}]):
            respuesta = self.client.post(self.editor, {"revision": 1, "secciones": json.dumps(secciones)})
            self.assertIn("secciones", respuesta.context["form"].errors)
        self.listado.refresh_from_db()
        self.assertEqual(self.listado.revision, 1)

    def test_publicacion_desactualizada_no_sobrescribe(self):
        self.client.force_login(self.admin)
        self.listado.revision = 2
        self.listado.save()
        respuesta = self.client.post(self.editor, {"revision": 1, "secciones": json.dumps(self.listado.secciones)})
        self.assertContains(respuesta, "Otro administrador modificó")
        self.listado.refresh_from_db()
        self.assertEqual(self.listado.revision, 2)

    def test_evidencias_exigen_rol(self):
        self.client.post(self.url, self.datos(respuesta_pared="no", observacion_pared="Hay un daño visible en la pared.", foto_pared=self.foto()))
        url = reverse("foto_integridad", args=[FotoIntegridad.objects.get().pk])
        for usuario in (None, self.persona):
            cliente = Client()
            if usuario:
                cliente.force_login(usuario)
            self.assertEqual(cliente.get(url).status_code, 302)
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        respuesta.close()
