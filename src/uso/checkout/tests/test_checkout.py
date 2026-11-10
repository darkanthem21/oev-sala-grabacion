import json
from datetime import date, time, timedelta
from unittest.mock import patch
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from agenda.models import Bloque
from personas.models import Area, Rol, Usuario
from solicitudes.models import Solicitud, SolicitudBloque
from uso.checkout.models import Checkout, FotoIntegridad, FormularioCheckout, RespuestaCheckout
from uso.checkout.services import casos_falta_integridad


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
        return {
            "revision": self.listado.revision, "hora_salida": "10:00", "respuesta_pared": "si",
            "asistencia": "si",
            "observaciones": "La sala se entrega revisada y en el estado indicado.", "foto_final": self.foto(), **cambios,
        }

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
        respuesta = self.client.get(self.editor)
        self.assertContains(respuesta, "Publicar listado")
        self.assertNotContains(respuesta, "Versión publicada")

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
        respuesta = self.client.post(self.url, {"asistencia": "si", "revision": 2, "hora_salida": "10:00", "respuesta_nuevo": "no"})
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

    def test_cierre_exige_observaciones_y_foto_aunque_todo_cumpla(self):
        datos = self.datos(observaciones="")
        del datos["foto_final"]
        respuesta = self.client.post(self.url, datos)
        self.assertIn("observaciones", respuesta.context["form"].errors)
        self.assertIn("foto_final", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_foto_final_falsa_es_rechazada(self):
        archivo = SimpleUploadedFile("final.png", b"archivo sin imagen", content_type="image/png")
        respuesta = self.client.post(self.url, self.datos(foto_final=archivo))
        self.assertIn("foto_final", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_foto_final_no_admite_gif(self):
        salida = BytesIO()
        Image.new("RGB", (4, 4)).save(salida, "GIF")
        archivo = SimpleUploadedFile("foto.gif", salida.getvalue(), content_type="image/gif")
        respuesta = self.client.post(self.url, self.datos(foto_final=archivo))
        self.assertIn("foto_final", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_foto_final_no_admite_mas_de_cinco_mb(self):
        archivo = self.foto()
        grande = SimpleUploadedFile("grande.png", archivo.read() + b"\0" * (5 * 1024 * 1024), content_type="image/png")
        respuesta = self.client.post(self.url, self.datos(foto_final=grande))
        self.assertIn("foto_final", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_observaciones_por_pregunta_y_recomendaciones_finales(self):
        respuesta = self.client.post(self.url, self.datos(
            respuesta_pared="no", observacion_pared="Hay un daño visible en la pared.", foto_pared=self.foto(),
            recomendacion_pared="Revisar el panel señalado en la fotografía.", recomendaciones="Mantener despejada la zona de trabajo.",
        ))
        self.assertEqual(respuesta.status_code, 302)
        registro = Checkout.objects.get()
        self.assertEqual(registro.recomendaciones, "Mantener despejada la zona de trabajo.")
        self.assertTrue(registro.foto_final.storage.exists(registro.foto_final.name))
        detalle = registro.respuestas_detalladas.get()
        self.assertEqual(detalle.texto, "¿La pared está sin daños?")
        self.assertEqual(detalle.observacion, "Hay un daño visible en la pared.")
        self.assertEqual(detalle.recomendacion, "")
        self.assertNotIn("recomendacion", registro.respuestas["pared"])
        self.assertEqual(detalle.foto.checkout, registro)
        self.assertEqual(detalle.foto.pregunta, "pared")

    def test_reporte_solo_incluye_incumplimientos(self):
        self.listado.secciones[0]["preguntas"].append({"id": "limpio", "texto": "¿La sala está limpia?"})
        self.listado.save()
        self.client.post(self.url, self.datos(
            respuesta_pared="no", observacion_pared="Hay un daño visible en la pared.", foto_pared=self.foto(),
            recomendacion_pared="Reparar el panel acústico.", respuesta_limpio="si",
        ))
        registro = Checkout.objects.get()
        self.assertEqual(registro.respuestas_detalladas.count(), 2)
        self.assertEqual(list(casos_falta_integridad(registro).values_list("pregunta", flat=True)), ["pared"])
        url = reverse("reporte_integridad", args=[self.ticket.ticket])
        respuesta = self.client.get(url)
        self.assertContains(respuesta, "¿La pared está sin daños?")
        self.assertContains(respuesta, "Hay un daño visible en la pared.")
        self.assertNotContains(respuesta, "Reparar el panel acústico.")
        self.assertNotContains(respuesta, "¿La sala está limpia?")
        self.assertContains(respuesta, "Descargar fotografía final")

    def test_reporte_sin_incidencias(self):
        self.client.post(self.url, self.datos())
        self.assertFalse(casos_falta_integridad().exists())
        respuesta = self.client.get(reverse("reporte_integridad", args=[self.ticket.ticket]))
        self.assertContains(respuesta, "No se registraron faltas de integridad")
        self.assertNotContains(respuesta, "¿La pared está sin daños?")

    def test_nuevos_accesos_protegidos(self):
        self.client.post(self.url, self.datos())
        registro = Checkout.objects.get()
        urls = [reverse("foto_cierre", args=[registro.pk]), reverse("reporte_integridad", args=[self.ticket.ticket])]
        self.client.force_login(self.persona)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.admin)
        for url in urls:
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200)
            respuesta.close()

    def test_reporte_no_disponible_sin_checkout(self):
        self.assertEqual(self.client.get(reverse("reporte_integridad", args=[self.ticket.ticket])).status_code, 404)

    def test_normalizacion_de_reportes_anteriores_conserva_evidencia(self):
        registro = Checkout.objects.create(
            ticket=self.ticket, formulario=self.listado.secciones, revision=1, hora_salida=time(10),
            respuestas={"pared": {"cumple": False, "observacion": "Daño registrado antes de la migración."}},
        )
        foto = FotoIntegridad.objects.create(checkout=registro, pregunta="pared", archivo="checkout/anterior.png")
        normalizar = import_module("uso.migrations.0003_normalizar_respuestas_existentes").normalizar
        normalizar(apps, SimpleNamespace(connection=connection))
        normalizar(apps, SimpleNamespace(connection=connection))
        detalle = registro.respuestas_detalladas.get()
        self.assertEqual(detalle.observacion, "Daño registrado antes de la migración.")
        self.assertEqual(detalle.foto.pk, foto.pk)
        self.assertEqual(detalle.foto.archivo.name, "checkout/anterior.png")
        self.assertFalse(registro.foto_final)
        self.assertEqual(casos_falta_integridad(registro).count(), 1)
        self.assertEqual(self.client.get(reverse("foto_cierre", args=[registro.pk])).status_code, 404)

    def test_vista_previa_solo_administracion(self):
        url = reverse("preview_checkout")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.admin)
        respuesta = self.client.get(url)
        self.assertContains(respuesta, "Vista previa del listado")
        self.assertContains(respuesta, "Registro de asistencia")
        self.assertFalse(Checkout.objects.exists())

    def test_vista_previa_muestra_borrador_sin_publicarlo(self):
        self.client.force_login(self.admin)
        borrador = [{"id": "nueva", "titulo": "Sección de prueba", "preguntas": [{"id": "prueba", "texto": "¿Pregunta del borrador?"}]}]
        respuesta = self.client.post(reverse("preview_checkout"), {
            "accion": "asistencia", "asistencia": "si", "revision": 1, "secciones": json.dumps(borrador),
        })
        self.assertContains(respuesta, "¿Pregunta del borrador?")
        self.assertNotContains(respuesta, "Recomendaciones sobre esta evidencia")
        self.assertNotIn("recomendacion_prueba", respuesta.context["form"].fields)
        self.assertFalse(respuesta.context["form"].is_bound)
        self.listado.refresh_from_db()
        self.assertNotEqual(self.listado.secciones, borrador)
        self.assertEqual(self.listado.revision, 1)
        self.assertFalse(Checkout.objects.exists())

    def test_prueba_valida_no_guarda_reporte_ni_fotografias(self):
        self.client.force_login(self.admin)
        archivos_antes = list(Path(self.directorio.name).rglob("*"))
        respuesta = self.client.post(reverse("preview_checkout"), self.datos(
            accion="probar", secciones=json.dumps(self.listado.secciones), respuesta_pared="no",
            observacion_pared="Daño de prueba para la vista previa.", foto_pared=self.foto(),
        ))
        self.assertContains(respuesta, "Prueba correcta")
        self.assertTrue(respuesta.context["validado"])
        self.assertFalse(Checkout.objects.exists())
        self.assertFalse(RespuestaCheckout.objects.exists())
        self.assertFalse(FotoIntegridad.objects.exists())
        self.assertEqual(list(Path(self.directorio.name).rglob("*")), archivos_antes)
        self.listado.refresh_from_db()
        self.assertEqual(self.listado.revision, 1)

    def test_prueba_detecta_no_sin_evidencia(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("preview_checkout"), self.datos(
            accion="probar", secciones=json.dumps(self.listado.secciones), respuesta_pared="no",
        ))
        self.assertFalse(respuesta.context["validado"])
        self.assertIn("observacion_pared", respuesta.context["form"].errors)
        self.assertIn("foto_pared", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_vista_previa_rechaza_borrador_invalido(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("preview_checkout"), {"revision": 1, "secciones": "[]"})
        self.assertTemplateUsed(respuesta, "uso/checkout/editor.html")
        self.assertIn("secciones", respuesta.context["form"].errors)
        self.listado.refresh_from_db()
        self.assertEqual(self.listado.revision, 1)

    def test_asistencia_se_pregunta_antes_del_listado(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Registro de asistencia")
        self.assertNotContains(respuesta, 'name="respuesta_pared"')
        self.assertFalse(respuesta.context["mostrar_listado"])
        self.assertFalse(Checkout.objects.exists())
        respuesta = self.client.post(self.url, {"asistencia": "si", "accion": "asistencia"})
        self.assertContains(respuesta, "¿La pared está sin daños?")
        self.assertFalse(respuesta.context["form"].is_bound)
        self.assertFalse(Checkout.objects.exists())

    def test_asistencia_es_obligatoria(self):
        datos = self.datos()
        del datos["asistencia"]
        respuesta = self.client.post(self.url, datos)
        self.assertIn("asistencia", respuesta.context["asistencia_form"].errors)
        self.assertFalse(Checkout.objects.exists())

    def test_inasistencia_no_requiere_formulario_ni_crea_incidencias(self):
        respuesta = self.client.post(self.url, {"asistencia": "no", "accion": "asistencia"})
        self.assertEqual(respuesta.status_code, 302)
        registro = Checkout.objects.get()
        self.assertFalse(registro.asistio)
        self.assertIsNone(registro.hora_salida)
        self.assertEqual(registro.respuestas, {})
        self.assertEqual(registro.observaciones, "")
        self.assertFalse(registro.foto_final)
        self.assertFalse(RespuestaCheckout.objects.exists())
        self.assertFalse(FotoIntegridad.objects.exists())
        self.assertContains(self.client.get(self.url), "Inasistencia registrada")
        reporte = self.client.get(reverse("reporte_integridad", args=[self.ticket.ticket]))
        self.assertContains(reporte, "No se realizó una revisión de integridad")

    def test_preview_prueba_inasistencia_sin_guardarla(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("preview_checkout"), {
            "accion": "probar", "asistencia": "no", "revision": 1, "secciones": json.dumps(self.listado.secciones),
        })
        self.assertContains(respuesta, "Prueba correcta")
        self.assertFalse(Checkout.objects.exists())
        respuesta = self.client.post(reverse("preview_checkout"), {
            "accion": "asistencia", "asistencia": "si", "revision": 1, "secciones": json.dumps(self.listado.secciones),
        })
        self.assertContains(respuesta, "¿La pared está sin daños?")
        respuesta = self.client.post(reverse("preview_checkout"), {
            "accion": "cambiar_asistencia", "revision": 1, "secciones": json.dumps(self.listado.secciones),
        })
        self.assertContains(respuesta, "Registro de asistencia")
        self.assertNotContains(respuesta, 'name="respuesta_pared"')
        self.assertFalse(respuesta.context["mostrar_listado"])
        self.assertFalse(Checkout.objects.exists())

    def test_edicion_conserva_fotografias_y_marca_editado(self):
        self.client.post(self.url, self.datos(respuesta_pared="no", observacion_pared="Daño original en el panel.", foto_pared=self.foto()))
        registro = Checkout.objects.get()
        fecha_original = registro.registrado_en
        foto_final = registro.foto_final.name
        foto_pregunta = registro.fotos.get().archivo.name
        url = reverse("editar_checkout", args=[self.ticket.ticket])
        datos = self.datos(respuesta_pared="no", observacion_pared="Daño corregido en la descripción del panel.")
        del datos["foto_final"]
        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.foto_final.name, foto_final)
        self.assertEqual(registro.fotos.get().archivo.name, foto_pregunta)
        self.assertEqual(registro.registrado_en, fecha_original)
        self.assertIsNotNone(registro.editado_en)
        self.assertEqual(registro.editado_por, self.apoyo)
        self.assertEqual(registro.ediciones.get().antes["respuestas"]["pared"]["observacion"], "Daño original en el panel.")
        self.assertContains(self.client.get(self.url), "Editado por")
        self.assertEqual(casos_falta_integridad(registro).get().observacion, "Daño corregido en la descripción del panel.")

    def test_edicion_bloqueada_despues_de_diez_minutos(self):
        self.client.post(self.url, self.datos())
        registro = Checkout.objects.get()
        Checkout.objects.filter(pk=registro.pk).update(registrado_en=timezone.now() - timedelta(minutes=10, seconds=1))
        url = reverse("editar_checkout", args=[self.ticket.ticket])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, self.datos()).status_code, 403)
        self.assertFalse(registro.ediciones.exists())
        self.assertNotContains(self.client.get(self.url), "Modificar check-out")

    def test_edicion_exactamente_en_el_limite_y_no_extiende_plazo(self):
        self.client.post(self.url, self.datos())
        registro = Checkout.objects.get()
        limite = registro.limite_edicion
        url = reverse("editar_checkout", args=[self.ticket.ticket])
        with patch("uso.checkout.models.timezone.now", return_value=limite):
            respuesta = self.client.post(url, self.datos())
        self.assertEqual(respuesta.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.limite_edicion, limite)
        with patch("uso.checkout.models.timezone.now", return_value=limite + timedelta(microseconds=1)):
            self.assertEqual(self.client.post(url, self.datos()).status_code, 403)

    def test_otro_apoyo_no_puede_editar(self):
        self.client.post(self.url, self.datos())
        otro = Usuario.objects.create_user(email="otro.edita@example.com")
        otro.groups.add(Group.objects.get(name=Rol.APOYO))
        self.client.force_login(otro)
        url = reverse("editar_checkout", args=[self.ticket.ticket])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"asistencia": "no"}).status_code, 403)
        self.assertTrue(Checkout.objects.get().asistio)

    def test_edicion_usa_listado_original(self):
        self.client.post(self.url, self.datos())
        self.listado.secciones[0]["preguntas"][0]["texto"] = "Pregunta distinta de una nueva publicación"
        self.listado.revision += 1
        self.listado.save()
        respuesta = self.client.get(reverse("editar_checkout", args=[self.ticket.ticket]))
        self.assertContains(respuesta, "¿La pared está sin daños?")
        self.assertNotContains(respuesta, "Pregunta distinta de una nueva publicación")

    def test_cambiar_asistencia_a_inasistencia_actualiza_reporte(self):
        self.client.post(self.url, self.datos(respuesta_pared="no", observacion_pared="Daño de prueba en la pared.", foto_pared=self.foto()))
        registro = Checkout.objects.get()
        foto_anterior = registro.fotos.get().archivo.name
        respuesta = self.client.post(reverse("editar_checkout", args=[self.ticket.ticket]), {"asistencia": "no"})
        self.assertEqual(respuesta.status_code, 302)
        registro.refresh_from_db()
        self.assertFalse(registro.asistio)
        self.assertFalse(casos_falta_integridad(registro).exists())
        self.assertFalse(registro.fotos.exists())
        self.assertEqual(registro.ediciones.get().antes["fotos"]["pared"], foto_anterior)

    def test_corregir_inasistencia_exige_listado_completo(self):
        self.client.post(self.url, {"asistencia": "no"})
        url = reverse("editar_checkout", args=[self.ticket.ticket])
        respuesta = self.client.post(url, {"asistencia": "si"})
        self.assertIn("foto_final", respuesta.context["form"].errors)
        self.assertFalse(Checkout.objects.get().asistio)
        respuesta = self.client.post(url, self.datos())
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Checkout.objects.get().asistio)

    def test_edicion_invalida_no_reemplaza_reporte(self):
        self.client.post(self.url, self.datos())
        registro = Checkout.objects.get()
        url = reverse("editar_checkout", args=[self.ticket.ticket])
        respuesta = self.client.post(url, self.datos(observaciones="corta"))
        self.assertEqual(respuesta.status_code, 200)
        registro.refresh_from_db()
        self.assertIsNone(registro.editado_en)
        self.assertFalse(registro.ediciones.exists())

    def test_cambiar_respuesta_a_si_elimina_incidencia_actual(self):
        self.client.post(self.url, self.datos(respuesta_pared="no", observacion_pared="Daño originalmente registrado.", foto_pared=self.foto()))
        registro = Checkout.objects.get()
        url = reverse("editar_checkout", args=[self.ticket.ticket])
        respuesta = self.client.post(url, self.datos(respuesta_pared="si"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(casos_falta_integridad(registro).exists())
        self.assertFalse(registro.fotos.exists())
        self.assertFalse(registro.ediciones.get().antes["respuestas"]["pared"]["cumple"])

    def test_codigos_invalidos_no_producen_error_de_servidor(self):
        for codigo in ("T-²", "T-" + "9" * 100, "T-9223372036854775808", "01", "T-00"):
            with self.subTest(codigo=codigo):
                self.assertEqual(self.client.get(reverse("checkout_apoyo", args=[codigo])).status_code, 404)
