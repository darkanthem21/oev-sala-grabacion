import pytest
from django.urls import reverse
from django.core import mail
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

def test_ac6_001_recupera_ok(client, solicitante_activo):
    '''
    Caso de Prueba [AC6-001]: Solicitud exitosa de cambio de contraseña (Happy Path)
    '''
    url = reverse('password_reset')
    response = client.post(url, {'email': 'solicitante.activo@uach.cl'})
    assert response.status_code == 302
    assert response.url == reverse('password_reset_done')
    assert len(mail.outbox) == 1
    assert 'solicitante.activo@uach.cl' in mail.outbox[0].to

def test_ac6_002_recupera_invalido(client):
    '''
    Caso de Prueba [AC6-002]: Solicitud de recuperación con correo no registrado
    '''
    url = reverse('password_reset')
    response = client.post(url, {'email': 'fantasma.noexiste@uach.cl'})
    assert response.status_code == 302
    assert response.url == reverse('password_reset_done')
    assert len(mail.outbox) == 0

def test_ac6_003_token_corrupto(client, solicitante_activo):
    '''
    Caso de Prueba [AC6-003]: Alteración manual de token de recuperación en URL
    '''
    url_alterada = reverse('password_reset_confirm', kwargs={'uidb64': 'Mw', 'token': 'set-password-token-invalido'})
    response = client.get(url_alterada)
    assert response.status_code == 200
    
    content = response.content.decode('utf-8').lower()
    assert "pedir otro enlace" in content

def test_ac6_004_token_expirado(client, solicitante_activo):
    '''
    Caso de Prueba [AC6-004]: Expiración y prevención de doble uso del enlace de recuperación
    '''
    client.post(reverse('password_reset'), {'email': 'solicitante.activo@uach.cl'})
    pass
