import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

def test_ac1_001_render_form(client):
    '''
    Caso de Prueba [AC1-001]: Verificación visual del formulario de inicio de sesión
    '''
    url = reverse('login_solicitante')
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert 'type="email"' in content or 'name="username"' in content or 'name="email"' in content
    assert 'type="password"' in content
    assert 'type="submit"' in content

def test_ac2_001_oculta_pass(client):
    '''
    Caso de Prueba [AC2-001]: Ocultamiento visual de la contraseña
    '''
    url = reverse('login_solicitante')
    response = client.get(url)
    assert response.status_code == 200
    assert 'type="password"' in response.content.decode('utf-8')
