import pytest
from django.urls import reverse
from personas.models import Usuario
from configuracion.models import Parametros, CambioParametro

pytestmark = pytest.mark.django_db

@pytest.fixture
def admin_user():
    '''
    Setup de usuario administrador para auditoría.
    '''
    user = Usuario.objects.create_user(
        email="admin.bitacora@uach.cl", 
        password="ClaveAdmin123", 
        is_staff=True
    )
    return user

@pytest.fixture
def parametros_base():
    '''
    Devuelve los parámetros iniciales.
    '''
    return Parametros.cargar()

def test_ac4_001_registro_cambios_bitacora(client, admin_user, parametros_base):
    '''
    Caso de Prueba [AC4-001]: Registro de cambios en la bitácora de configuración
    '''
    client.force_login(admin_user)
    url = reverse('panel_reglas')
    
    # Cambiamos un parámetro controlable
    post_data = {
        'pedir_dia': parametros_base.pedir_dia,
        'pedir_hora': parametros_base.pedir_hora.strftime('%H:%M'),
        'semanas_desfase': parametros_base.semanas_desfase, 
        'plazo_confirmacion_dias': parametros_base.plazo_confirmacion_dias,
        'tope_mensual': parametros_base.tope_mensual,
        'max_bloques_solicitud': parametros_base.max_bloques_solicitud,
        'inasistencias_para_sancion': parametros_base.inasistencias_para_sancion,
        'dias_sancion': 45, # Cambiado de 30 a 45
        'intentos_maximos': parametros_base.intentos_maximos,
        'minutos_bloqueo': parametros_base.minutos_bloqueo,
        'terminos': parametros_base.terminos
    }
    
    cantidad_cambios_antes = CambioParametro.objects.count()
    
    response = client.post(url, post_data)
    assert response.status_code == 302
    
    # Validar que la tabla de auditoría capturó la transacción
    assert CambioParametro.objects.count() == cantidad_cambios_antes + 1
    
    # El modelo ordena por "-cuando", la primera fila será el último cambio registrado
    ultimo_cambio = CambioParametro.objects.first()
    
    assert ultimo_cambio.campo == 'dias_sancion'
    assert ultimo_cambio.antes == '30'
    assert ultimo_cambio.despues == '45'
    assert ultimo_cambio.quien == admin_user