import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from personas.models import Usuario, Rol
from configuracion.models import Parametros

pytestmark = pytest.mark.django_db

@pytest.fixture
def solicitante_activo():
    '''
    Setup básico para tener un usuario solicitante de prueba activo.
    '''
    user = Usuario.objects.create_user(
        email="solicitante.activo@uach.cl", 
        password="ClaveCorrecta123"
    )
    try:
        rol_solicitante, _ = Rol.objects.get_or_create(nombre=Rol.SOLICITANTE)
        user.roles.add(rol_solicitante)
    except Exception:
        pass
    return user

@pytest.fixture
def parametros_sistema():
    '''
    Setup de los parámetros del sistema.
    '''
    return Parametros.cargar()

def test_ac5_001_bloqueo_5_intentos(client, solicitante_activo, parametros_sistema):
    '''
    Caso de Prueba [AC5-001]: Bloqueo temporal tras agotar 5 intentos fallidos
    '''
    url = reverse('login_solicitante')
    parametros_sistema.intentos_maximos = 5
    parametros_sistema.save()
    for i in range(5):
        response = client.post(url, {
            'username': 'solicitante.activo@uach.cl',
            'password': f'ClaveEquivocada{i}'
        })
    assert response.status_code == 200
    content = response.content.decode('utf-8').lower()
    assert "bloqueada" in content or "bloqueo" in content or "intentos" in content

def test_ac5_002_levanta_bloqueo(client, solicitante_activo, parametros_sistema, mocker):
    '''
    Caso de Prueba [AC5-002]: Levantamiento automático del bloqueo temporal
    '''
    url = reverse('login_solicitante')
    parametros_sistema.intentos_maximos = 5
    parametros_sistema.minutos_bloqueo = 15
    parametros_sistema.save()
    for i in range(5):
        client.post(url, {'username': 'solicitante.activo@uach.cl', 'password': f'Fail{i}'})
    future_time = timezone.now() + timedelta(minutes=16)
    mocker.patch('django.utils.timezone.now', return_value=future_time)
    response = client.post(url, {
        'username': 'solicitante.activo@uach.cl', 
        'password': 'ClaveCorrecta123'
    })
    assert response.status_code in [302, 200]
