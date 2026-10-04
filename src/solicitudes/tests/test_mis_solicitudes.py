from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agenda.models import Bloque, Dia, primera_fecha_pedible
from configuracion.models import Parametros
from personas.models import Area, Rol
from solicitudes.models import Solicitud, SolicitudBloque
from solicitudes.views import SOLICITUDES_POR_PAGINA

Usuario = get_user_model()


class MisSolicitudesTestCase(TestCase):
    """US-09: el solicitante ve bloque, fecha y estado de cada solicitud suya."""

    def setUp(self):
        self.area = Area.objects.create(nombre="Informática", activa=True)
        self.usuario = self._solicitante("docente@uach.cl")
        self.client.force_login(self.usuario)

        fecha_minima = primera_fecha_pedible()
        self.fecha = fecha_minima + date.resolution * ((Dia.JUEVES - fecha_minima.weekday()) % 7)
        self.bloques = list(Bloque.objects.filter(dia=Dia.JUEVES, activo=True)[:2])

    def _solicitante(self, correo):
        usuario = Usuario.objects.create_user(email=correo, password="testpassword123")
        usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        usuario.areas.add(self.area)
        return usuario

    def _solicitud(self, usuario, bloques, **estados):
        solicitud = Solicitud.objects.create(
            solicitante=usuario, area=self.area, motivo="Grabar clase", **estados
        )
        for bloque in bloques:
            SolicitudBloque.objects.create(solicitud=solicitud, bloque=bloque, fecha=self.fecha)
        return solicitud

    def test_requiere_ingreso_de_solicitante(self):
        self.client.logout()
        response = self.client.get(reverse("mis_solicitudes"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login_solicitante"), response["Location"])

    def test_sin_solicitudes_muestra_aviso(self):
        response = self.client.get(reverse("mis_solicitudes"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/mis_solicitudes.html")
        self.assertContains(response, "Aún no has realizado solicitudes")

    def test_muestra_bloques_fecha_y_estado(self):
        solicitud = self._solicitud(self.usuario, self.bloques)
        response = self.client.get(reverse("mis_solicitudes"))

        self.assertContains(response, f"#{solicitud.id}")
        self.assertContains(response, f'datetime="{self.fecha.isoformat()}"')
        self.assertContains(response, self.fecha.strftime("%d/%m/%Y"))
        for bloque in self.bloques:
            self.assertContains(response, f"{bloque.inicio:%H:%M} – {bloque.termino:%H:%M}")
        self.assertContains(response, "En revisión por la Oficina")
        self.assertContains(response, "estado-revision")

    def test_refleja_cada_estado_de_la_solicitud(self):
        casos = [
            ({"estado_validacion": Solicitud.EstadoValidacion.RECHAZADA}, "Rechazada"),
            ({"estado_validacion": Solicitud.EstadoValidacion.ACEPTADA}, "Aceptada"),
            ({"estado_validacion": Solicitud.EstadoValidacion.ACEPTADA,
              "estado_confirmacion": Solicitud.EstadoConfirmacion.PENDIENTE}, "Pendiente de confirmación"),
            ({"estado_validacion": Solicitud.EstadoValidacion.ACEPTADA,
              "estado_confirmacion": Solicitud.EstadoConfirmacion.CONFIRMADA}, "Confirmada"),
            ({"estado_validacion": Solicitud.EstadoValidacion.ACEPTADA,
              "estado_confirmacion": Solicitud.EstadoConfirmacion.CANCELADA}, "Cancelada"),
        ]
        for estados, etiqueta in casos:
            with self.subTest(etiqueta=etiqueta):
                Solicitud.objects.all().delete()
                self._solicitud(self.usuario, self.bloques[:1], **estados)
                response = self.client.get(reverse("mis_solicitudes"))
                self.assertContains(response, etiqueta)

    def test_muestra_solicitudes_de_todas_las_areas_con_su_area(self):
        otra_area = Area.objects.create(nombre="Medicina", activa=True)
        self.usuario.areas.add(otra_area)
        de_informatica = self._solicitud(self.usuario, self.bloques[:1])
        de_medicina = self._solicitud(self.usuario, self.bloques[1:])
        de_medicina.area = otra_area
        de_medicina.save()

        response = self.client.get(reverse("mis_solicitudes"))
        self.assertCountEqual(response.context["pagina"].object_list, [de_informatica, de_medicina])
        self.assertContains(response, '<th scope="col">Área</th>', html=True)
        self.assertContains(response, '<td data-titulo="Área">Informática</td>', html=True)
        self.assertContains(response, '<td data-titulo="Área">Medicina</td>', html=True)

    def test_no_muestra_solicitudes_de_otros(self):
        ajena = self._solicitud(self._solicitante("otro@uach.cl"), self.bloques[:1])
        propia = self._solicitud(self.usuario, self.bloques[1:])
        response = self.client.get(reverse("mis_solicitudes"))
        self.assertEqual(list(response.context["pagina"].object_list), [propia])
        self.assertNotContains(response, f"#{ajena.id}<")


class PaginacionMisSolicitudesTestCase(TestCase):
    """US-09: el historial se pagina de a 20 y htmx cambia solo la tabla."""

    def setUp(self):
        self.area = Area.objects.create(nombre="Informática", activa=True)
        self.usuario = Usuario.objects.create_user(email="docente@uach.cl", password="testpassword123")
        self.usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.usuario.areas.add(self.area)
        self.client.force_login(self.usuario)
        # Sin bloques: la paginación no depende de ellos y así no chocan las
        # validaciones de bloque ya pedido.
        Solicitud.objects.bulk_create(
            Solicitud(solicitante=self.usuario, area=self.area, motivo=f"Clase {n}")
            for n in range(SOLICITUDES_POR_PAGINA + 5)
        )
        self.url = reverse("mis_solicitudes")

    def _ids(self, response):
        return [s.id for s in response.context["pagina"].object_list]

    def test_primera_pagina_trae_veinte_y_enlace_a_la_siguiente(self):
        response = self.client.get(self.url)
        pagina = response.context["pagina"]
        self.assertEqual(len(pagina.object_list), SOLICITUDES_POR_PAGINA)
        self.assertEqual(pagina.paginator.num_pages, 2)
        self.assertContains(response, "Página 1 de 2")
        self.assertContains(response, f'hx-get="{self.url}?vista=proximas&amp;pagina=2"')
        self.assertContains(response, 'hx-target="#historial"')
        self.assertContains(response, 'hx-push-url="true"')

    def test_ultima_pagina_trae_el_resto_sin_repetir(self):
        primera = self._ids(self.client.get(self.url))
        segunda = self._ids(self.client.get(self.url, {"pagina": 2}))
        self.assertEqual(len(segunda), 5)
        self.assertFalse(set(primera) & set(segunda))
        self.assertEqual(
            sorted(primera + segunda),
            sorted(Solicitud.objects.values_list("id", flat=True)),
        )

    def test_pagina_invalida_no_rompe(self):
        for valor, esperada in [("abc", 1), ("999", 2), ("-1", 2)]:
            with self.subTest(pagina=valor):
                response = self.client.get(self.url, {"pagina": valor})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["pagina"].number, esperada)

    def test_htmx_recibe_solo_la_tabla(self):
        response = self.client.get(self.url, {"pagina": 2}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "solicitudes/_tabla_historial.html")
        self.assertTemplateNotUsed(response, "solicitudes/mis_solicitudes.html")
        self.assertNotContains(response, "<html")
        self.assertContains(response, 'id="historial"')
        self.assertIn("HX-Request", response["Vary"])

    def test_sin_htmx_o_al_restaurar_historial_recibe_la_pagina_entera(self):
        for cabeceras in [{}, {"HTTP_HX_REQUEST": "true", "HTTP_HX_HISTORY_RESTORE_REQUEST": "true"}]:
            with self.subTest(cabeceras=cabeceras):
                response = self.client.get(self.url, {"pagina": 2}, **cabeceras)
                self.assertTemplateUsed(response, "solicitudes/mis_solicitudes.html")
                self.assertContains(response, "<html")

    def test_con_una_sola_pagina_no_muestra_controles(self):
        Solicitud.objects.filter(id__in=self._ids(self.client.get(self.url))).delete()
        response = self.client.get(self.url)
        self.assertNotContains(response, 'class="paginacion"')


class ProximasAnterioresTestCase(TestCase):
    """US-09: el historial separa las solicitudes por si sus fechas ya pasaron."""

    def setUp(self):
        self.area = Area.objects.create(nombre="Informática", activa=True)
        self.usuario = Usuario.objects.create_user(email="docente@uach.cl", password="testpassword123")
        self.usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.usuario.areas.add(self.area)
        self.client.force_login(self.usuario)
        self.bloque = Bloque.objects.filter(activo=True).first()
        self.hoy = timezone.localdate()
        self.url = reverse("mis_solicitudes")

    def _solicitud(self, *fechas):
        # bulk_create se salta la regla de anticipación de SolicitudBloque.clean,
        # que impide registrar fechas pasadas.
        solicitud = Solicitud.objects.create(solicitante=self.usuario, area=self.area, motivo="Grabar")
        SolicitudBloque.objects.bulk_create(
            SolicitudBloque(solicitud=solicitud, bloque=self.bloque, fecha=f) for f in fechas
        )
        return solicitud

    def _ids(self, **params):
        response = self.client.get(self.url, params)
        return [s.id for s in response.context["pagina"].object_list]

    def test_separa_por_fecha_y_hoy_cuenta_como_proxima(self):
        pasada = self._solicitud(self.hoy - timedelta(days=3))
        de_hoy = self._solicitud(self.hoy)
        futura = self._solicitud(self.hoy + timedelta(days=7))

        self.assertCountEqual(self._ids(), [de_hoy.id, futura.id])
        self.assertEqual(self._ids(vista="anteriores"), [pasada.id])

    def test_con_un_bloque_pendiente_sigue_siendo_proxima(self):
        mixta = self._solicitud(self.hoy - timedelta(days=1), self.hoy + timedelta(days=1))
        self.assertEqual(self._ids(), [mixta.id])
        self.assertEqual(self._ids(vista="anteriores"), [])

    def test_orden_proximas_por_cercania_y_anteriores_por_recencia(self):
        lejana = self._solicitud(self.hoy + timedelta(days=20))
        cercana = self._solicitud(self.hoy + timedelta(days=2))
        antigua = self._solicitud(self.hoy - timedelta(days=30))
        reciente = self._solicitud(self.hoy - timedelta(days=2))

        self.assertEqual(self._ids(), [cercana.id, lejana.id])
        self.assertEqual(self._ids(vista="anteriores"), [reciente.id, antigua.id])

    def test_vista_por_defecto_e_invalida_son_proximas(self):
        for params in [{}, {"vista": "otra"}]:
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assertEqual(response.context["vista"], "proximas")
                self.assertRegex(
                    response.content.decode(),
                    r'pestana-historial activa"\s+href="[^"]*\?vista=proximas"',
                )

    def test_pestanas_muestran_cuentas_y_usan_htmx(self):
        self._solicitud(self.hoy - timedelta(days=1))
        self._solicitud(self.hoy + timedelta(days=1))
        self._solicitud(self.hoy + timedelta(days=2))

        response = self.client.get(self.url)
        self.assertEqual(response.context["total_proximas"], 2)
        self.assertEqual(response.context["total_anteriores"], 1)
        self.assertContains(response, f'hx-get="{self.url}?vista=anteriores"')

        response = self.client.get(self.url, {"vista": "anteriores"}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "solicitudes/_tabla_historial.html")
        self.assertTemplateNotUsed(response, "solicitudes/mis_solicitudes.html")

    def test_pestana_vacia_tiene_su_propio_aviso(self):
        self._solicitud(self.hoy + timedelta(days=1))
        response = self.client.get(self.url, {"vista": "anteriores"})
        self.assertContains(response, "Aún no tienes solicitudes con fechas pasadas.")
        self.assertNotContains(response, "Aún no has realizado solicitudes")

    def test_paginacion_conserva_la_vista(self):
        Solicitud.objects.bulk_create(
            Solicitud(solicitante=self.usuario, area=self.area, motivo=f"Clase {n}")
            for n in range(SOLICITUDES_POR_PAGINA + 1)
        )
        ids = list(Solicitud.objects.values_list("id", flat=True))
        SolicitudBloque.objects.bulk_create(
            SolicitudBloque(solicitud_id=i, bloque=self.bloque, fecha=self.hoy - timedelta(days=1))
            for i in ids
        )
        response = self.client.get(self.url, {"vista": "anteriores"})
        self.assertContains(response, f'hx-get="{self.url}?vista=anteriores&amp;pagina=2"')
        self.assertEqual(len(self._ids(vista="anteriores", pagina=2)), 1)

    def test_nota_de_confirmacion_solo_en_proximas(self):
        nota = "Confirma tu asistencia."
        self.assertContains(self.client.get(self.url), nota)
        self.assertNotContains(self.client.get(self.url, {"vista": "anteriores"}), nota)

    def test_nota_de_confirmacion_usa_el_plazo_configurado(self):
        parametros = Parametros.cargar()
        casos = [
            (2, "recibirás una notificación 2 días antes", "a más tardar el día anterior"),
            (5, "recibirás una notificación 5 días antes", "a más tardar el día anterior"),
            (1, "recibirás una notificación el día anterior", "ese mismo día"),
        ]
        for plazo, aviso, limite in casos:
            with self.subTest(plazo=plazo):
                parametros.plazo_confirmacion_dias = plazo
                parametros.save()
                # Sin depender de cómo la plantilla corta las líneas.
                texto = " ".join(self.client.get(self.url).content.decode().split())
                self.assertIn(aviso, texto)
                self.assertIn(limite, texto)
