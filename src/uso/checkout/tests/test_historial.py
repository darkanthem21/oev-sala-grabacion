from datetime import date, datetime, time, timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader

from agenda.models import Bloque
from personas.models import Area, Rol, Usuario
from solicitudes.models import Solicitud, SolicitudBloque
from uso.checkout.historial import inicio_historial, registros_recientes
from uso.checkout.models import Checkout, FotoIntegridad, RespuestaCheckout


class HistorialCheckoutTests(TestCase):
    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        configuracion = override_settings(MEDIA_ROOT=temporal.name)
        configuracion.enable()
        self.addCleanup(configuracion.disable)
        self.admin = Usuario.objects.create_user(email="admin.historial@example.com", is_staff=True)
        self.apoyo = Usuario.objects.create_user(email="apoyo.historial@example.com")
        self.apoyo.groups.add(Group.objects.get(name=Rol.APOYO))
        self.persona = Usuario.objects.create_user(email="persona.historial@example.com", first_name="María", last_name="Pérez")
        self.area = Area.objects.create(nombre="Área de pruebas")
        self.ahora = timezone.make_aware(datetime(2026, 11, 2, 12))
        self.contador = 0
        self.url = reverse("historial_checkout")
        self.client.force_login(self.admin)

    def registro(self, fecha=None, cumple=True, asistio=True):
        self.contador += 1
        minuto = self.contador
        bloque = Bloque.objects.create(dia=4, inicio=time(22, minuto), termino=time(22, minuto + 1))
        solicitud = Solicitud.objects.create(
            solicitante=self.persona, area=self.area, fecha=date(2026, 10, 30), motivo="Prueba historial",
            estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
        )
        ticket = SolicitudBloque.objects.create(solicitud=solicitud, bloque=bloque)
        listado = [{"id": "integridad", "titulo": "Integridad de la sala", "preguntas": [{"id": "pared", "texto": "¿La pared está sin daños?"}]}]
        registro = Checkout.objects.create(
            ticket=ticket, formulario=listado, revision=1, asistio=asistio, registrado_por=self.apoyo,
            hora_salida=time(9) if asistio else None,
            respuestas={"pared": {"cumple": cumple, "observacion": "Panel con daño <visible> & revisión." if not cumple else ""}} if asistio else {},
            observaciones="La sala se entrega en las condiciones descritas." if asistio else "",
        )
        Checkout.objects.filter(pk=registro.pk).update(registrado_en=fecha or self.ahora - timedelta(hours=1))
        registro.refresh_from_db()
        if asistio:
            RespuestaCheckout.objects.create(
                checkout=registro, pregunta="pared", texto="¿La pared está sin daños?", seccion="Integridad de la sala",
                cumple=cumple, observacion=registro.respuestas["pared"]["observacion"],
            )
        return registro

    def get(self, url=None, **parametros):
        with patch("uso.checkout.historial.timezone.now", return_value=self.ahora):
            return self.client.get(url or self.url, parametros)

    def leer_pdf(self, registro):
        respuesta = self.get(reverse("pdf_checkout", args=[registro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn("inline", respuesta["Content-Disposition"])
        datos = b"".join(respuesta.streaming_content)
        respuesta.close()
        self.assertTrue(datos.startswith(b"%PDF-"))
        return PdfReader(BytesIO(datos))

    def test_pestanas_editor_e_historial(self):
        self.assertContains(self.get(reverse("panel_checkout")), "Historial")
        self.assertContains(self.get(), "Formulario")

    def test_dos_meses_calendario_y_cambio_de_anio(self):
        self.assertEqual(inicio_historial(date(2026, 4, 30)), date(2026, 2, 28))
        self.assertEqual(inicio_historial(date(2024, 4, 30)), date(2024, 2, 29))
        self.assertEqual(inicio_historial(date(2026, 1, 31)), date(2025, 11, 30))

    def test_limite_inclusivo_no_borra_registros_anteriores(self):
        limite = timezone.make_aware(datetime(2026, 9, 2))
        incluido = self.registro(limite)
        antiguo = self.registro(limite - timedelta(microseconds=1))
        self.assertEqual(list(registros_recientes(self.ahora).values_list("pk", flat=True)), [incluido.pk])
        self.assertTrue(Checkout.objects.filter(pk=antiguo.pk).exists())
        self.assertEqual(self.get(reverse("pdf_checkout", args=[antiguo.pk])).status_code, 404)
        respuesta = self.get(semana="2026-08-31")
        self.assertEqual(respuesta.context["pagina"].paginator.count, 1)

    def test_semanas_descendentes_y_dias_descendentes(self):
        primero = self.registro(timezone.make_aware(datetime(2026, 11, 1, 12)))
        self.registro(timezone.make_aware(datetime(2026, 11, 1, 10)))
        self.registro(timezone.make_aware(datetime(2026, 10, 31, 16)))
        respuesta = self.get(semana="2026-10-26")
        semanas = [s["lunes"] for s in respuesta.context["semanas"]]
        self.assertEqual(semanas, sorted(semanas, reverse=True))
        self.assertEqual([d["fecha"] for d in respuesta.context["dias"]], [date(2026, 11, 1), date(2026, 10, 31)])
        self.assertEqual(respuesta.context["dias"][0]["registros"][0].pk, primero.pk)

    def test_estado_reporte_e_inasistencia_y_datos_del_usuario(self):
        self.registro(cumple=False)
        self.registro(cumple=True)
        self.registro(asistio=False)
        respuesta = self.get()
        self.assertContains(respuesta, "Sí · Con reporte")
        self.assertContains(respuesta, "No · Sin incumplimientos")
        self.assertContains(respuesta, "No · Inasistencia")
        self.assertContains(respuesta, "María Pérez")
        self.assertContains(respuesta, self.apoyo.email)
        self.assertContains(respuesta, "30/10/2026")

    def test_semana_invalida_vuelve_a_actual_y_semana_vacia(self):
        for valor in ("invalida", "2030-01-07", "2026-10-28"):
            respuesta = self.get(semana=valor)
            self.assertEqual(respuesta.context["semana"]["lunes"], date(2026, 11, 2))
            self.assertContains(respuesta, "No hay check-outs registrados")

    def test_paginacion_conserva_semana(self):
        for i in range(31):
            self.registro(self.ahora - timedelta(minutes=i + 1))
        respuesta = self.get()
        self.assertEqual(len(respuesta.context["pagina"].object_list), 30)
        self.assertContains(respuesta, "semana=2026-11-02&amp;pagina=2")
        respuesta = self.get(semana="2026-11-02", pagina="2")
        self.assertEqual(len(respuesta.context["pagina"].object_list), 1)

    def test_pdf_e_historial_exigen_administracion(self):
        registro = self.registro()
        for usuario in (self.apoyo, self.persona):
            self.client.force_login(usuario)
            self.assertEqual(self.get().status_code, 302)
            self.assertEqual(self.get(reverse("pdf_checkout", args=[registro.pk])).status_code, 302)
        self.client.logout()
        self.assertEqual(self.get().status_code, 302)

    def test_registros_futuros_no_aparecen(self):
        registro = self.registro(self.ahora + timedelta(seconds=1))
        self.assertFalse(registros_recientes(self.ahora).exists())
        self.assertEqual(self.get(reverse("pdf_checkout", args=[registro.pk])).status_code, 404)

    def test_pdf_formulario_completo_con_imagenes_y_tipografias(self):
        registro = self.registro(cumple=False)
        registro.formulario[0]["preguntas"].append({"id": "puerta", "texto": "¿La puerta funciona?"})
        registro.respuestas["puerta"] = {"cumple": True, "observacion": ""}
        imagen = BytesIO()
        Image.new("RGB", (12, 12), "white").save(imagen, "PNG")
        registro.foto_final = SimpleUploadedFile("cierre.png", imagen.getvalue(), content_type="image/png")
        registro.editado_en = self.ahora
        registro.editado_por = self.apoyo
        registro.save()
        FotoIntegridad.objects.create(checkout=registro, pregunta="pared", archivo=SimpleUploadedFile("pared.png", imagen.getvalue(), content_type="image/png"))
        pdf = self.leer_pdf(registro)
        texto = "\n".join(p.extract_text() for p in pdf.pages)
        for esperado in ("María Pérez", "¿La pared está sin daños?", "¿La puerta funciona?", "<visible>", "Observaciones finales", "Fotografía final", "Editado por"):
            self.assertIn(esperado, texto)
        fuentes = [str(f.get_object().get("/BaseFont", "")) for pagina in pdf.pages for f in pagina["/Resources"]["/Font"].values()]
        self.assertTrue(any("Roboto" in f for f in fuentes))
        self.assertTrue(any("Montserrat" in f for f in fuentes))
        imagenes = [obj for p in pdf.pages for obj in p["/Resources"].get("/XObject", {}).values() if obj.get_object().get("/Subtype") == "/Image"]
        self.assertGreaterEqual(len(imagenes), 2)

    def test_pdf_de_inasistencia_no_inventa_respuestas(self):
        pdf = self.leer_pdf(self.registro(asistio=False))
        texto = "\n".join(p.extract_text() for p in pdf.pages)
        self.assertIn("Inasistencia", texto)
        self.assertNotIn("¿La pared está sin daños?", texto)

    def test_pdf_multiplagina_y_foto_no_disponible(self):
        registro = self.registro(cumple=False)
        registro.respuestas["pared"]["observacion"] = ("Observación extensa del estado de la sala. " * 110) + " FIN OBSERVACION"
        registro.foto_final = "checkout/cierre/no-existe.png"
        registro.save()
        pdf = self.leer_pdf(registro)
        self.assertGreater(len(pdf.pages), 1)
        texto = "\n".join(p.extract_text() for p in pdf.pages)
        self.assertIn("FIN OBSERVACION", texto)
        self.assertIn("imagen no disponible", texto)

    def test_respuesta_historica_ausente_se_muestra_igual_en_pantalla_y_pdf(self):
        registro = self.registro()
        registro.respuestas = {}
        registro.save()
        self.client.force_login(self.apoyo)
        respuesta = self.get(reverse("checkout_apoyo", args=[registro.ticket.ticket]))
        self.assertContains(respuesta, "Sin respuesta registrada")
        self.client.force_login(self.admin)
        pdf = self.leer_pdf(registro)
        self.assertIn("Sin respuesta registrada", "\n".join(p.extract_text() for p in pdf.pages))
