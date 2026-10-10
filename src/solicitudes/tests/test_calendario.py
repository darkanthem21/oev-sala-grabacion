from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from agenda.models import Bloque, Dia, primera_fecha_pedible, Bloqueo
from personas.models import Area, Rol
from solicitudes.models import Solicitud, SolicitudBloque


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
        for dia in ["LUN", "MAR", "MIE", "JUE", "VIE"]:
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