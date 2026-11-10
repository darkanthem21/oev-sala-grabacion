from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque, Dia, primera_fecha_pedible, Bloqueo
from personas.models import Area, Rol
from solicitudes.models import Solicitud, SolicitudBloque
from solicitudes.services import obtener_bloques_dia_para_usuario
from solicitudes.wizard import SolicitudWizard


class CalendarioSolicitudesTestCase(TestCase):
    def setUp(self):
        self.bloque_disponible = Bloque.objects.filter(dia=Dia.JUEVES, activo=True).first()
        self.user = get_user_model().objects.create_user(email="s1@uv.cl", password="123")
        self.user.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.client.force_login(self.user)

        fecha_minima = primera_fecha_pedible()
        self.fecha_prueba = fecha_minima + date.resolution * ((Dia.JUEVES - fecha_minima.weekday()) % 7)

    def test_ac7_001_renderizado_calendario_mensual(self):
        '''
        Caso de Prueba [AC7-001]: Renderizado del calendario mensual (Lunes a Viernes)
        '''
        url = reverse("calendario")
        response = self.client.get(f"{url}?year={self.fecha_prueba.year}&month={self.fecha_prueba.month}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solicitudes/calendario.html")
        
        # Validar despliegue de semana hábil
        for dia in ["Lun", "Mar", "Mié", "Jue", "Vie"]:
            self.assertContains(response, f">{dia}</th>")
            
        # Comprobar la ausencia de Fines de Semana habilitados en la matriz
        self.assertNotContains(response, '<td class="sat available')
        self.assertNotContains(response, '<td class="sun available')

    def test_ac9_001_interaccion_dias_disponibles(self):
        '''
        Caso de Prueba [AC9-001]: Interacción exclusiva con días disponibles
        '''
        # Válida un día con bloques listos para marcar (Fecha 1)
        url_bloques = reverse("bloques_dia")
        response = self.client.get(f"{url_bloques}?fecha={self.fecha_prueba.isoformat()}")
        self.assertContains(response, "Disponible")
        self.assertContains(response, f'value="{self.bloque_disponible.id}"')
        
        # Crea e inyecta un bloqueo para una fecha futura (Fecha 2)
        fecha_bloqueada = self.fecha_prueba + timedelta(days=1)
        Bloqueo.objects.create(desde=fecha_bloqueada, hasta=fecha_bloqueada, motivo="evento")
        
        # Comprueba que el componente de bloques retorna vacío para esa fecha inhabilitada
        response_bloqueado = self.client.get(f"{url_bloques}?fecha={fecha_bloqueada.isoformat()}")
        self.assertContains(response_bloqueado, "No hay bloques disponibles para esta fecha")

    def test_bloque_con_solicitud_aceptada_no_esta_disponible_en_bloques_dia(self):
        area = Area.objects.create(nombre="Área Test", activa=True)
        solicitud_aceptada = Solicitud.objects.create(
            solicitante=self.user,
            area=area,
            fecha=self.fecha_prueba,
            motivo="Motivo test",
            personas=1,
            estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
            estado_confirmacion=Solicitud.EstadoConfirmacion.CONFIRMADA,
        )
        SolicitudBloque.objects.create(
            solicitud=solicitud_aceptada,
            bloque=self.bloque_disponible,
        )

        url = reverse("bloques_dia")
        response = self.client.get(f"{url}?fecha={self.fecha_prueba.isoformat()}")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'value="{self.bloque_disponible.id}"')

class QuienesDeMiUnidadTestCase(TestCase):
    """Dentro del asistente, cada bloque dice quiénes de la misma área lo piden."""

    def setUp(self):
        self.bloque = Bloque.objects.filter(dia=Dia.JUEVES, activo=True).first()
        fecha_minima = primera_fecha_pedible()
        self.fecha = fecha_minima + date.resolution * ((Dia.JUEVES - fecha_minima.weekday()) % 7)
        self.area = Area.objects.create(nombre="Historia", activa=True)
        self.otra_area = Area.objects.create(nombre="Química", activa=True)

        Usuario = get_user_model()
        self.user = Usuario.objects.create_user(email="yo@uv.cl", password="123")
        self.user.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
        self.user.areas.add(self.area)
        self.colega = Usuario.objects.create_user(
            email="colega@uv.cl", password="123", first_name="Ana", last_name="Rojas"
        )
        self.ajeno = Usuario.objects.create_user(
            email="ajeno@uv.cl", password="123", first_name="Beto", last_name="Soto"
        )
        self._pedir(self.colega, self.area)
        self._pedir(self.ajeno, self.otra_area)

        self.client.force_login(self.user)
        sesion = self.client.session
        sesion[SolicitudWizard.CLAVE_SESION] = {"area_id": self.area.id, "area_nombre": self.area.nombre}
        sesion.save()

    def _pedir(self, usuario, area, **extra):
        s = Solicitud.objects.create(solicitante=usuario, area=area, fecha=self.fecha, motivo="x", **extra)
        SolicitudBloque.objects.create(solicitud=s, bloque=self.bloque)
        return s

    def _panel(self, asistente=True):
        url = f"{reverse('bloques_dia')}?fecha={self.fecha.isoformat()}"
        return self.client.get(url + ("&paso=1" if asistente else ""))

    def test_en_el_asistente_muestra_solo_los_de_su_area(self):
        response = self._panel()
        self.assertContains(response, "Ana Rojas")
        self.assertContains(response, f'aria-describedby="unidad-{self.bloque.id}"')
        self.assertNotContains(response, "Beto Soto")

    def test_dice_explicitamente_la_unidad(self):
        # Puede tener varias áreas, pero pide para una: la que eligió.
        self.user.areas.add(self.otra_area)
        self.assertContains(self._panel(), "De Historia, también solicitan el bloque:")
        sesion = self.client.session
        sesion[SolicitudWizard.CLAVE_SESION] = {"area_id": self.otra_area.id, "area_nombre": self.otra_area.nombre}
        sesion.save()
        response = self._panel()
        self.assertContains(response, "De Química, también solicitan el bloque:")
        self.assertContains(response, "Beto Soto")
        self.assertNotContains(response, "Ana Rojas")

    def test_fuera_del_asistente_no_hay_nombres(self):
        response = self._panel(asistente=False)
        self.assertNotContains(response, "Ana Rojas")
        self.assertNotContains(response, 'class="lista-unidad"')
        # La cantidad se sigue mostrando.
        self.assertContains(response, "<strong>2</strong> personas")

    def test_un_area_que_ya_no_es_suya_no_muestra_nombres(self):
        self.user.areas.clear()
        self.assertNotContains(self._panel(), "Ana Rojas")

    def test_no_se_lista_a_si_mismo_ni_a_retiradas(self):
        self._pedir(self.user, self.area)
        Solicitud.objects.filter(solicitante=self.colega).update(
            estado_validacion=Solicitud.EstadoValidacion.RETIRADA
        )
        bloque = next(
            b for b in obtener_bloques_dia_para_usuario(self.fecha, usuario=self.user, area_id=self.area.id)
            if b.id == self.bloque.id
        )
        self.assertEqual(bloque.de_mi_unidad, [])

    def test_el_calendario_del_asistente_pide_el_panel_con_nombres(self):
        response = self.client.get(
            f"{reverse('calendario')}?year={self.fecha.year}&month={self.fecha.month}&paso=1"
        )
        self.assertContains(response, f"/solicitar/bloques/?fecha={self.fecha.isoformat()}&amp;paso=1")
