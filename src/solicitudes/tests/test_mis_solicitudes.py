from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque, Dia, primera_fecha_pedible
from personas.models import Area, Rol
from solicitudes.models import Solicitud, SolicitudBloque

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
        self.assertCountEqual(response.context["solicitudes"], [de_informatica, de_medicina])
        self.assertContains(response, '<th scope="col">Área</th>', html=True)
        self.assertContains(response, '<td data-titulo="Área">Informática</td>', html=True)
        self.assertContains(response, '<td data-titulo="Área">Medicina</td>', html=True)

    def test_no_muestra_solicitudes_de_otros(self):
        ajena = self._solicitud(self._solicitante("otro@uach.cl"), self.bloques[:1])
        propia = self._solicitud(self.usuario, self.bloques[1:])
        response = self.client.get(reverse("mis_solicitudes"))
        self.assertEqual(list(response.context["solicitudes"]), [propia])
        self.assertNotContains(response, f"#{ajena.id}<")
