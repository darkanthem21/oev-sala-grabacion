from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from agenda.models import Bloque, Dia, primera_fecha_pedible
from personas.models import Area
from solicitudes.forms import FechaReservaForm, SeleccionHorarioForm
from solicitudes.models import Solicitud, SolicitudBloque
from solicitudes.wizard import SolicitudWizard, obtener_limites_reserva

Usuario = get_user_model()


def _datos(fecha, *bloques):
    return MultiValueDict({"fecha": [fecha], "bloques": [str(b) for b in bloques]})


class FechaReservaFormTestCase(TestCase):
    def test_acepta_un_dia_dentro_de_los_limites(self):
        minima, _ = obtener_limites_reserva()
        self.assertEqual(FechaReservaForm.fecha_de(minima.isoformat()), minima)

    def test_rechaza_formato_vacio_y_fuera_de_periodo(self):
        minima, maxima = obtener_limites_reserva()
        for texto in ["", "19/10/2026", "abc", (minima - timedelta(days=1)).isoformat(),
                      (maxima + timedelta(days=1)).isoformat()]:
            with self.subTest(texto=texto):
                self.assertIsNone(FechaReservaForm.fecha_de(texto))

    def test_fuera_de_periodo_tiene_su_codigo(self):
        minima, _ = obtener_limites_reserva()
        form = FechaReservaForm({"fecha": (minima - timedelta(days=1)).isoformat()})
        self.assertTrue(form.has_error("fecha", code="fuera_de_periodo"))


class SeleccionHorarioFormTestCase(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Informática", activa=True)
        self.usuario = Usuario.objects.create_user(email="docente@uach.cl", password="x")
        minima = primera_fecha_pedible()
        self.fecha = minima + date.resolution * ((Dia.JUEVES - minima.weekday()) % 7)
        self.b1, self.b2 = Bloque.objects.filter(dia=Dia.JUEVES, activo=True)[:2]

    def _ocupar(self, bloque, usuario, **estados):
        solicitud = Solicitud.objects.create(
            solicitante=usuario, area=self.area, fecha=self.fecha, motivo="x", **estados
        )
        SolicitudBloque.objects.create(solicitud=solicitud, bloque=bloque)

    def _form(self, *bloques, exigir_todos=True):
        return SeleccionHorarioForm(
            _datos(self.fecha.isoformat(), *bloques), usuario=self.usuario, exigir_todos=exigir_todos
        )

    def test_valida_y_devuelve_los_bloques_del_dia(self):
        form = self._form(self.b1.id, self.b2.id)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual([b.id for b in form.cleaned_data["bloques"]], [self.b1.id, self.b2.id])

    def test_exige_al_menos_un_bloque(self):
        form = self._form()
        self.assertFalse(form.is_valid())
        self.assertIn("al menos un bloque", form.errors["bloques"][0])

    def test_ids_que_no_son_numeros(self):
        form = SeleccionHorarioForm(_datos(self.fecha.isoformat(), "x"), usuario=self.usuario)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.ids_enviados, [])

    def test_bloque_aceptado_de_otro_segun_exigir_todos(self):
        otro = Usuario.objects.create_user(email="otro@uach.cl", password="x")
        self._ocupar(self.b1, otro, estado_validacion=Solicitud.EstadoValidacion.ACEPTADA)

        self.assertFalse(self._form(self.b1.id, self.b2.id).is_valid())
        parcial = self._form(self.b1.id, self.b2.id, exigir_todos=False)
        self.assertTrue(parcial.is_valid(), parcial.errors)
        self.assertEqual([b.id for b in parcial.cleaned_data["bloques"]], [self.b2.id])
        self.assertFalse(self._form(self.b1.id, exigir_todos=False).is_valid())

    def test_rechaza_en_el_paso_1_un_bloque_propio_pendiente(self):
        self._ocupar(self.b1, self.usuario)
        form = self._form(self.b1.id)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.ids_enviados, [self.b1.id])


class AjustarAreaTestCase(TestCase):
    """SolicitudWizard.ajustar_area: cuándo se elige sola el área y cuándo hay que escogerla."""

    def setUp(self):
        self.informatica = Area.objects.create(nombre="Informática", activa=True)
        self.medicina = Area.objects.create(nombre="Medicina", activa=True)

    def _wizard(self, **datos):
        return SolicitudWizard({SolicitudWizard.CLAVE_SESION: datos} if datos else {})

    def test_con_una_sola_area_la_fija_sin_preguntar(self):
        wizard = self._wizard()
        self.assertIsNone(wizard.ajustar_area([self.informatica]))
        self.assertEqual(wizard.area_id, self.informatica.id)

    def test_si_la_unica_area_cambio_se_borra_el_horario(self):
        wizard = self._wizard(area_id=self.medicina.id, area_nombre="Medicina", fecha="2026-10-19", bloques_ids=[1])
        self.assertIsNone(wizard.ajustar_area([self.informatica]))
        self.assertEqual(wizard.area_id, self.informatica.id)
        self.assertIsNone(wizard.fecha_str)
        self.assertEqual(wizard.bloques_ids, [])

    def test_con_varias_areas_pide_elegir_o_cambiar(self):
        areas = [self.informatica, self.medicina]
        self.assertEqual(self._wizard().ajustar_area(areas), "elegir")
        vigente = self._wizard(area_id=self.medicina.id, area_nombre="Medicina")
        self.assertIsNone(vigente.ajustar_area(areas))
        retirada = Area.objects.create(nombre="Química", activa=False)
        vieja = self._wizard(area_id=retirada.id, area_nombre="Química")
        self.assertEqual(vieja.ajustar_area(areas), "cambiar")
