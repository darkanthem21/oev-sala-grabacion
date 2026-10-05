import pytest
from django.urls import reverse
from personas.models import Usuario, Rol

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

def test_ac3_001_login_ok(client, solicitante_activo):
    '''
    Caso de Prueba [AC3-001]: Inicio de sesión exitoso y redirección (Happy Path)
    '''
    url = reverse('login_solicitante')
    response = client.post(url, {
        'username': 'solicitante.activo@uach.cl',
        'password': 'ClaveCorrecta123'
    })
    assert response.status_code == 302
    assert response.url == reverse('solicitar') or response.url.startswith('/')

def test_ac4_001_error_correo(client):
    '''
    Caso de Prueba [AC4-001]: Intento de ingreso con correo no registrado
    '''
    url = reverse('login_solicitante')
    response = client.post(url, {
        'username': 'correo.noexiste@uach.cl',
        'password': 'ClaveCualquiera1'
    })
    assert response.status_code == 200
    content = response.content.decode('utf-8').lower()
    assert "incorrecto" in content or "error" in content

def test_ac4_002_error_pass(client, solicitante_activo):
    '''
    Caso de Prueba [AC4-002]: Intento de ingreso con contraseña incorrecta
    '''
    url = reverse('login_solicitante')
    response = client.post(url, {
        'username': 'solicitante.activo@uach.cl',
        'password': 'ClaveEquivocada999'
    })
    assert response.status_code == 200
    content = response.content.decode('utf-8').lower()
    assert "incorrecto" in content or "error" in content

def test_ac4_003_error_ambos(client):
    '''
    Caso de Prueba [AC4-003]: Intento de ingreso con correo y contraseña erróneos
    '''
    url = reverse('login_solicitante')
    response = client.post(url, {
        'username': 'invalido@uach.cl',
        'password': 'Invalida123'
    })
    assert response.status_code == 200
    content = response.content.decode('utf-8').lower()
    assert "incorrecto" in content or "error" in content
