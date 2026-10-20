"""US-10 desde el lado del solicitante: formulario bloqueado, POST directo
rechazado, aviso en todas sus páginas, Mis sanciones y la decisión de AC6."""
from datetime import date, datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from agenda.models import Bloque, Dia, primera_fecha_pedible
from personas.models import Area, Rol, Sancion, Usuario
from solicitudes.models import Solicitud, SolicitudBloque
from solicitudes.services import confirmar_solicitud, guardar_solicitud_completa, resolver

pytestmark = pytest.mark.django_db

SANTIAGO = ZoneInfo("America/Santiago")
FRANJA = 'class="franja-sancion"'


@pytest.fixture
def area():
    return Area.objects.create(nombre="Informática", activa=True)


def crear_solicitante(correo, area):
    usuario = Usuario.objects.create_user(email=correo, password="x")
    usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
    usuario.areas.add(area)
    return usuario


@pytest.fixture
def solicitante(area):
    return crear_solicitante("docente@uach.cl", area)


@pytest.fixture
def hoy():
    return timezone.localdate()


@pytest.fixture
def sancion(solicitante, hoy):
    return Sancion.objects.create(
        usuario=solicitante, inicio=hoy, termino=hoy + timedelta(days=7), motivo="No se presentó dos veces",
    )


@pytest.fixture
def jueves():
    """El primer jueves que se puede pedir, con sus bloques."""
    minima = primera_fecha_pedible()
    fecha = minima + timedelta(days=(Dia.JUEVES - minima.weekday()) % 7)
    return fecha, list(Bloque.objects.filter(dia=Dia.JUEVES, activo=True)[:1])


def crear_solicitud(usuario, area, fecha, bloques, **estados):
    solicitud = Solicitud.objects.create(solicitante=usuario, area=area, fecha=fecha, motivo="Grabar clase", **estados)
    for bloque in bloques:
        SolicitudBloque.objects.create(solicitud=solicitud, bloque=bloque)
    return solicitud


# --- T2: formulario bloqueado ---

@pytest.mark.parametrize("ruta", ["solicitar", "solicitar_area"])
def test_formulario_bloqueado_con_motivo_y_fecha_de_regreso(client, solicitante, sancion, ruta):
    client.force_login(solicitante)
    respuesta = client.get(reverse(ruta))
    assert respuesta.status_code == 200
    assert "solicitudes/sancionado.html" in [t.name for t in respuesta.templates]
    contenido = respuesta.content.decode()
    assert "No se presentó dos veces" in contenido
    assert f"Desde el {sancion.rehabilita}" in contenido
    assert "23:59" in contenido
    # La franja no se repite en la pantalla que ya lo dice en grande.
    assert FRANJA not in contenido


def test_sin_sancion_el_formulario_sigue_igual(client, solicitante):
    client.force_login(solicitante)
    respuesta = client.get(reverse("solicitar"), follow=True)
    assert "solicitudes/sancionado.html" not in [t.name for t in respuesta.templates]
    assert "solicitudes/solicitar.html" in [t.name for t in respuesta.templates]


def test_post_directo_al_ultimo_paso_no_crea_la_solicitud(client, solicitante, area, sancion, jueves):
    """La sesión trae el asistente completo, como si la sanción hubiera llegado
    con la pestaña abierta en el paso 3."""
    fecha, bloques = jueves
    client.force_login(solicitante)
    sesion = client.session
    sesion["solicitud_reserva"] = {
        "area_id": area.id, "area_nombre": area.nombre,
        "fecha": fecha.isoformat(), "bloques_ids": [b.id for b in bloques], "bloques_texto": "",
        "motivo": "Grabación", "observaciones": "", "personas": 1, "acompanantes": [],
    }
    sesion.save()

    respuesta = client.post(f"{reverse('solicitar')}?paso=3", {"paso": "confirmacion", "acepta_terminos": "on"})

    assert respuesta.status_code == 200
    assert "solicitudes/sancionado.html" in [t.name for t in respuesta.templates]
    assert not Solicitud.objects.exists()


def test_el_servicio_rechaza_aunque_no_pase_por_la_vista(solicitante, area, sancion, jueves):
    fecha, bloques = jueves
    with pytest.raises(ValidationError, match="sanción vigente"):
        guardar_solicitud_completa(solicitante, {
            "area_id": area.id, "fecha": fecha.isoformat(), "bloques_ids": [b.id for b in bloques],
            "motivo": "Grabación", "personas": 1, "acompanantes": [],
        })
    assert not Solicitud.objects.exists()


def test_al_dia_siguiente_del_termino_vuelve_a_poder_pedir(client, solicitante, sancion):
    """Rehabilitación automática con la fecha simulada: nadie la levanta."""
    al_terminar = sancion.termino
    ultimo_minuto = datetime(al_terminar.year, al_terminar.month, al_terminar.day, 23, 59, tzinfo=SANTIAGO)
    with mock.patch("django.utils.timezone.now", return_value=ultimo_minuto):
        client.force_login(solicitante)
        respuesta = client.get(reverse("solicitar"), follow=True)
        assert "solicitudes/sancionado.html" in [t.name for t in respuesta.templates]

    siguiente = al_terminar + timedelta(days=1)
    medianoche = datetime(siguiente.year, siguiente.month, siguiente.day, 0, 0, tzinfo=SANTIAGO)
    with mock.patch("django.utils.timezone.now", return_value=medianoche):
        client.force_login(solicitante)
        respuesta = client.get(reverse("solicitar"), follow=True)
        assert "solicitudes/sancionado.html" not in [t.name for t in respuesta.templates]
        assert FRANJA not in respuesta.content.decode()


# --- T3: aviso en todas las páginas del solicitante ---

@pytest.mark.parametrize("ruta", ["mis_solicitudes", "mis_sanciones"])
def test_aviso_visible_en_las_paginas_del_solicitante(client, solicitante, sancion, ruta):
    client.force_login(solicitante)
    contenido = client.get(reverse(ruta)).content.decode()
    assert FRANJA in contenido
    assert sancion.hasta in contenido


def test_aviso_visible_al_confirmar_asistencia(client, solicitante, area, sancion, jueves):
    fecha, bloques = jueves
    aceptada = crear_solicitud(solicitante, area, fecha, bloques, estado_validacion=Solicitud.EstadoValidacion.ACEPTADA)
    client.force_login(solicitante)
    respuesta = client.get(reverse("confirmar_solicitud", args=[aceptada.pk]))
    assert FRANJA in respuesta.content.decode()


def test_sin_sancion_no_hay_aviso(client, solicitante):
    client.force_login(solicitante)
    assert FRANJA not in client.get(reverse("mis_solicitudes")).content.decode()


def test_sancion_levantada_ya_no_avisa(client, solicitante, sancion):
    sancion.levantada_en = timezone.now()
    sancion.save()
    client.force_login(solicitante)
    assert FRANJA not in client.get(reverse("mis_solicitudes")).content.decode()


# --- T4: Mis sanciones ---

def test_mis_sanciones_vigente_primero_y_despues_las_pasadas(client, solicitante, sancion, hoy):
    Sancion.objects.create(
        usuario=solicitante, inicio=hoy - timedelta(days=60), termino=hoy - timedelta(days=30),
        motivo="Dejó la sala desordenada",
    )
    client.force_login(solicitante)
    contenido = client.get(reverse("mis_sanciones")).content.decode()
    vigente = contenido.index("No se presentó dos veces")
    pasada = contenido.index("Dejó la sala desordenada")
    assert contenido.index("Vigente") < vigente < contenido.index("Anteriores") < pasada
    assert f"{sancion.inicio:%d/%m/%Y}" in contenido and f"{sancion.termino:%d/%m/%Y}" in contenido


def test_mis_sanciones_no_muestra_las_de_otro(client, solicitante, area, hoy):
    otro = crear_solicitante("otro@uach.cl", area)
    Sancion.objects.create(usuario=otro, inicio=hoy, termino=hoy + timedelta(days=3), motivo="Motivo ajeno")
    client.force_login(solicitante)
    contenido = client.get(reverse("mis_sanciones")).content.decode()
    assert "Motivo ajeno" not in contenido
    assert "No tienes sanciones vigentes" in contenido


def test_mis_sanciones_muestra_el_levantamiento(client, solicitante, sancion):
    sancion.levantada_en = timezone.now()
    sancion.motivo_levantamiento = "Presentó certificado médico"
    sancion.save()
    client.force_login(solicitante)
    contenido = client.get(reverse("mis_sanciones")).content.decode()
    assert "Presentó certificado médico" in contenido
    assert "No tienes sanciones vigentes" in contenido


def test_mis_sanciones_pide_ingresar(client):
    respuesta = client.get(reverse("mis_sanciones"))
    assert respuesta.status_code == 302
    assert reverse("login_solicitante") in respuesta["Location"]


def test_enlace_a_mis_sanciones_en_el_encabezado(client, solicitante):
    client.force_login(solicitante)
    contenido = client.get(reverse("mis_solicitudes")).content.decode()
    assert f'href="{reverse("mis_sanciones")}"' in contenido


# --- AC6 (decidido el 20/10): las reservas aprobadas se mantienen ---

def test_ac6_la_reserva_aceptada_se_mantiene_y_se_puede_confirmar(solicitante, area, hoy, jueves):
    fecha, bloques = jueves
    aceptada = crear_solicitud(solicitante, area, fecha, bloques, estado_validacion=Solicitud.EstadoValidacion.ACEPTADA)

    Sancion.objects.create(usuario=solicitante, inicio=hoy, termino=fecha + timedelta(days=7), motivo="Sanción")

    aceptada.refresh_from_db()
    assert aceptada.estado_validacion == Solicitud.EstadoValidacion.ACEPTADA
    assert aceptada.estado_confirmacion == Solicitud.EstadoConfirmacion.NO_HABILITADA
    assert confirmar_solicitud(solicitante, aceptada.pk)


def test_ac6_la_pendiente_queda_igual_y_el_validador_la_puede_aprobar(solicitante, area, hoy, jueves):
    fecha, bloques = jueves
    pendiente = crear_solicitud(solicitante, area, fecha, bloques)
    validador = Usuario.objects.create_user(email="valida@uach.cl", password="x")

    Sancion.objects.create(usuario=solicitante, inicio=hoy, termino=fecha + timedelta(days=7), motivo="Sanción")

    pendiente.refresh_from_db()
    assert pendiente.estado_validacion == Solicitud.EstadoValidacion.PENDIENTE
    resolver(pendiente.pk, True, "", validador)
    pendiente.refresh_from_db()
    assert pendiente.estado_validacion == Solicitud.EstadoValidacion.ACEPTADA
