import pytest
from datetime import timedelta
from django.urls import reverse
from django.contrib.auth.models import Group
from personas.models import Usuario, Rol, Area
from configuracion.models import Parametros
from solicitudes.models import Solicitud, SolicitudBloque
from agenda.models import Bloque, Dia, primera_fecha_pedible

pytestmark = pytest.mark.django_db

@pytest.fixture
def admin_user():
    '''
    Setup básico para tener un administrador (staff) activo.
    '''
    user = Usuario.objects.create_user(
        email="admin.config@uach.cl", 
        password="ClaveAdmin123", 
        is_staff=True
    )
    return user

@pytest.fixture
def solicitante_user():
    '''
    Setup básico para un usuario solicitante de prueba activo.
    '''
    user = Usuario.objects.create_user(
        email="solicitante.config@uach.cl", 
        password="ClaveCorrecta123"
    )
    grupo, _ = Group.objects.get_or_create(name=Rol.SOLICITANTE)
    user.groups.add(grupo)
    return user

@pytest.fixture
def parametros_base():
    '''
    Fija y retorna los parámetros por defecto de la base de datos.
    '''
    return Parametros.cargar()

def test_ac1_001_carga_edicion_parametros(client, admin_user, parametros_base):
    '''
    Caso de Prueba [AC1-001]: Carga y edición de parámetros de configuración
    '''
    client.force_login(admin_user)
    url = reverse('panel_reglas')
    
    # Validamos que cargue con valores por defecto
    response = client.get(url)
    assert response.status_code == 200
    assert 'value="1"' in response.content.decode('utf-8')  # semanas_desfase
    assert 'value="8"' in response.content.decode('utf-8')  # tope_mensual
    
    # Editamos algunos parámetros
    post_data = {
        'pedir_dia': parametros_base.pedir_dia,
        'pedir_hora': parametros_base.pedir_hora.strftime('%H:%M'),
        'semanas_desfase': 2,       # Cambio
        'plazo_confirmacion_dias': parametros_base.plazo_confirmacion_dias,
        'tope_mensual': 10,         # Cambio
        'max_bloques_solicitud': parametros_base.max_bloques_solicitud,
        'inasistencias_para_sancion': parametros_base.inasistencias_para_sancion,
        'dias_sancion': parametros_base.dias_sancion,
        'intentos_maximos': parametros_base.intentos_maximos,
        'minutos_bloqueo': parametros_base.minutos_bloqueo,
        'terminos': parametros_base.terminos
    }
    
    response_post = client.post(url, post_data)
    assert response_post.status_code == 302
    assert response_post.url == url
    
    # Validamos persistencia
    parametros_actualizados = Parametros.cargar()
    assert parametros_actualizados.semanas_desfase == 2
    assert parametros_actualizados.tope_mensual == 10

def test_ac3_001_independencia_estado_reservas(client, admin_user, solicitante_user, parametros_base):
    '''
    Caso de Prueba [AC3-001]: Independencia de estado en reservas previas al modificar límites
    '''
    area = Area.objects.create(nombre="Informática", activa=True)
    fecha_minima = primera_fecha_pedible()
    fecha_reserva = fecha_minima + timedelta(days=((Dia.JUEVES - fecha_minima.weekday()) % 7))
    
    # Simular una solicitud de 3 bloques enviada previamente
    solicitud = Solicitud.objects.create(
        solicitante=solicitante_user,
        area=area,
        fecha=fecha_reserva,
        motivo="Reserva previa de 3 bloques",
        estado_validacion=Solicitud.EstadoValidacion.PENDIENTE
    )
    
    # Extraer o crear 3 bloques
    bloques = list(Bloque.objects.filter(activo=True)[:3])
    if len(bloques) < 3:
        for i in range(3):
            bloques.append(Bloque.objects.create(dia=Dia.LUNES, inicio=f"0{8+i}:00", termino=f"0{9+i}:00", activo=True))
            
    for b in bloques:
        SolicitudBloque.objects.create(solicitud=solicitud, bloque=b)

    assert solicitud.solicitudes_bloques.count() == 3

    # El administrador reduce el límite máximo de bloques por solicitud a 1
    client.force_login(admin_user)
    post_data = {
        'pedir_dia': parametros_base.pedir_dia,
        'pedir_hora': parametros_base.pedir_hora.strftime('%H:%M'),
        'semanas_desfase': parametros_base.semanas_desfase,
        'plazo_confirmacion_dias': parametros_base.plazo_confirmacion_dias,
        'tope_mensual': parametros_base.tope_mensual,
        'max_bloques_solicitud': 1, # Reducido a 1
        'inasistencias_para_sancion': parametros_base.inasistencias_para_sancion,
        'dias_sancion': parametros_base.dias_sancion,
        'intentos_maximos': parametros_base.intentos_maximos,
        'minutos_bloqueo': parametros_base.minutos_bloqueo,
        'terminos': parametros_base.terminos
    }
    client.post(reverse('panel_reglas'), post_data)
    
    # Comprobar que la regla no tiene retroactividad y la reserva antigua no se anula
    solicitud.refresh_from_db()
    assert solicitud.solicitudes_bloques.count() == 3
    assert solicitud.estado_validacion == Solicitud.EstadoValidacion.PENDIENTE

def test_ac5_001_edicion_terminos_condiciones(client, admin_user, solicitante_user, parametros_base):
    '''
    Caso de Prueba [AC5-001]: Edición dinámica de términos y condiciones sin recompilación
    '''
    # El administrador inyecta los nuevos términos
    client.force_login(admin_user)
    nuevos_terminos = "Nuevos términos de servicio inyectados en runtime para validación 2026."
    
    post_data = {
        'pedir_dia': parametros_base.pedir_dia,
        'pedir_hora': parametros_base.pedir_hora.strftime('%H:%M'),
        'semanas_desfase': parametros_base.semanas_desfase,
        'plazo_confirmacion_dias': parametros_base.plazo_confirmacion_dias,
        'tope_mensual': parametros_base.tope_mensual,
        'max_bloques_solicitud': parametros_base.max_bloques_solicitud,
        'inasistencias_para_sancion': parametros_base.inasistencias_para_sancion,
        'dias_sancion': parametros_base.dias_sancion,
        'intentos_maximos': parametros_base.intentos_maximos,
        'minutos_bloqueo': parametros_base.minutos_bloqueo,
        'terminos': nuevos_terminos
    }
    client.post(reverse('panel_reglas'), post_data)

    # El solicitante carga el Paso 3 del wizard donde se presentan los términos
    client.force_login(solicitante_user)
    
    # Setup de sesión simulando que el usuario ya completó el Paso 1 y 2
    session = client.session
    area = Area.objects.create(nombre="Términos", activa=True)
    solicitante_user.areas.add(area)
    # El paso 3 vuelve a validar el horario: el bloque tiene que ser del día de la fecha.
    fecha = primera_fecha_pedible()
    bloque = Bloque.objects.filter(dia=fecha.weekday(), activo=True).order_by("inicio").first()
    session["solicitud_reserva"] = {
        "area_id": area.id,
        "area_nombre": area.nombre,
        "motivo": "Prueba visual de términos",
        "fecha": fecha.isoformat(),
        "bloques_ids": [bloque.id],
    }
    session.save()

    response = client.get(f"{reverse('solicitar')}?paso=3")
    assert response.status_code == 200
    
    # Comprobar que los nuevos términos se presentan de inmediato a los clientes
    content = response.content.decode('utf-8')
    assert nuevos_terminos in content