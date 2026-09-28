"""US-07. Los datos de prueba tienen que calzar con el sistema real: si piden un
bloque que la jornada no tiene o mas personas de las que admite el formulario,
el panel se veria bien con datos imposibles."""
from collections import defaultdict
from datetime import date
from importlib import import_module

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from agenda.models import Dia
from solicitudes import validacion
from solicitudes.forms import MAXIMO_PERSONAS

# La jornada por defecto que carga agenda: no se copia, se importa.
HORARIO = import_module("agenda.migrations.0002_jornada_por_defecto").HORARIO
JORNADA = {(i.strftime("%H:%M"), t.strftime("%H:%M")) for i, t in HORARIO}


class DatosDePrueba(SimpleTestCase):
    def setUp(self):
        self.datos = validacion.cargar()
        self.areas = {a["id"] for a in self.datos["areas"]}

    def pedidos(self):
        for s in self.datos["solicitudes"]:
            for b in s["bloques"]:
                yield s, b

    def test_se_declaran_de_prueba(self):
        self.assertEqual(validacion.ORIGEN, "prueba")
        self.assertIn("DATOS DE PRUEBA", self.datos["_aviso"])

    def test_cada_solicitud_apunta_a_un_area_existente(self):
        for s in self.datos["solicitudes"]:
            self.assertIn(s["area"], self.areas, s["id"])

    def test_personas_calzan_con_el_formulario_de_t4(self):
        for s in self.datos["solicitudes"]:
            self.assertTrue(1 <= s["personas"] <= MAXIMO_PERSONAS, s["id"])
            self.assertEqual(len(s["acompanantes"]), s["personas"] - 1, s["id"])

    def test_la_jornada_del_json_es_la_de_agenda(self):
        """La grilla de la semana se dibuja con la jornada del JSON: si no es la
        real, el cuadro mostraria horas que el sistema no tiene."""
        del_json = {(b["inicio"], b["termino"]) for b in self.datos["jornada"]}
        self.assertEqual(del_json, JORNADA)

    def test_los_bloques_existen_en_la_jornada(self):
        for s, b in self.pedidos():
            self.assertIn((b["inicio"], b["termino"]), JORNADA, (s["id"], b["ticket"]))

    def test_el_dia_calza_con_la_fecha(self):
        for s, b in self.pedidos():
            dia = date.fromisoformat(b["fecha"]).weekday()
            self.assertLess(dia, 5, b["ticket"])
            self.assertEqual(Dia(dia).label, b["dia"], b["ticket"])

    def test_los_tickets_no_se_repiten(self):
        tickets = [b["ticket"] for _, b in self.pedidos()]
        self.assertEqual(len(tickets), len(set(tickets)))

    def test_hay_una_solicitud_compitiendo_en_dos_bloques_distintos(self):
        """El caso que el mockup no dejaba ver: T-01 y T-02 son la misma solicitud."""
        grupos = defaultdict(set)
        for s, b in self.pedidos():
            grupos[(b["fecha"], b["inicio"])].add(s["id"])
        en_competencia = defaultdict(int)
        for solicitudes in grupos.values():
            if len(solicitudes) > 1:
                for sid in solicitudes:
                    en_competencia[sid] += 1
        self.assertTrue(any(n >= 2 for n in en_competencia.values()), dict(en_competencia))


class AccesoAlPanel(TestCase):
    url = reverse("panel_validador")

    def test_la_administracion_lo_ve_con_el_aviso_de_prueba(self):
        staff = get_user_model().objects.create_user("validador@prueba.local", "clave-larga-123", is_staff=True)
        self.client.force_login(staff)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Datos de prueba")
        self.assertContains(respuesta, 'id="datos-panel"')

    def test_un_solicitante_no_entra(self):
        comun = get_user_model().objects.create_user("comun@prueba.local", "clave-larga-123")
        self.client.force_login(comun)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login_gestion"), respuesta["Location"])

    def test_sin_sesion_no_entra(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
