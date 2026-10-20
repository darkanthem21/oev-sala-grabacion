"""US-10: el modelo Sancion, su administración y la pestaña Sanciones del panel."""
from datetime import date, datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from personas import services
from personas.models import Sancion, Usuario

pytestmark = pytest.mark.django_db

SANTIAGO = ZoneInfo("America/Santiago")


def a_las(fecha, hora, minuto=0):
    """Un instante en la hora de Santiago, que es la que manda en las fechas."""
    return datetime(fecha.year, fecha.month, fecha.day, hora, minuto, tzinfo=SANTIAGO)


@pytest.fixture
def persona():
    return Usuario.objects.create_user(email="docente@uach.cl", password="x")


@pytest.fixture
def hoy():
    return timezone.localdate()


def sancionar(usuario, inicio, termino, motivo="No se presentó dos veces"):
    return Sancion.objects.create(usuario=usuario, inicio=inicio, termino=termino, motivo=motivo)


# --- Vigencia (T1, T7) ---

def test_vigente_desde_el_primer_dia_hasta_el_dia_de_termino(persona):
    sancion = sancionar(persona, date(2026, 11, 2), date(2026, 11, 6))
    for dia in (date(2026, 11, 2), date(2026, 11, 4), date(2026, 11, 6)):
        assert list(Sancion.objects.vigentes(dia)) == [sancion], dia
    assert not Sancion.objects.pasadas(date(2026, 11, 6)).exists()


def test_deja_de_regir_el_dia_siguiente_al_termino(persona):
    sancion = sancionar(persona, date(2026, 11, 2), date(2026, 11, 6))
    assert not Sancion.objects.vigentes(date(2026, 11, 7)).exists()
    assert list(Sancion.objects.pasadas(date(2026, 11, 7))) == [sancion]


def test_rehabilitacion_automatica_a_medianoche(persona):
    """El último minuto del día de término todavía sanciona; el primero del día
    siguiente ya no, sin que nadie haga nada."""
    sancion = sancionar(persona, date(2026, 11, 2), date(2026, 11, 6))
    with mock.patch("django.utils.timezone.now", return_value=a_las(date(2026, 11, 6), 23, 59)):
        assert persona.sancion_vigente == sancion
    with mock.patch("django.utils.timezone.now", return_value=a_las(date(2026, 11, 7), 0, 0)):
        assert persona.sancion_vigente is None


def test_la_fecha_es_la_de_santiago_y_no_la_utc(persona):
    """A las 22:00 del 6 en Santiago ya es el 7 en UTC: todavía rige."""
    sancion = sancionar(persona, date(2026, 11, 2), date(2026, 11, 6))
    with mock.patch("django.utils.timezone.now", return_value=a_las(date(2026, 11, 6), 22, 0)):
        assert persona.sancion_vigente == sancion


def test_levantada_deja_de_regir_aunque_no_haya_terminado(persona, hoy):
    sancion = sancionar(persona, hoy, hoy + timedelta(days=10))
    services.levantar(sancion, None, "Se justificó la inasistencia")
    assert persona.sancion_vigente is None
    assert list(Sancion.objects.pasadas()) == [sancion]


def test_entre_dos_vigentes_manda_la_que_termina_despues(persona, hoy):
    sancionar(persona, hoy, hoy + timedelta(days=3))
    larga = sancionar(persona, hoy, hoy + timedelta(days=20))
    assert persona.sancion_vigente == larga


def test_la_sancion_de_otro_no_cuenta(persona, hoy):
    otro = Usuario.objects.create_user(email="otro@uach.cl", password="x")
    sancionar(otro, hoy, hoy + timedelta(days=5))
    assert persona.sancion_vigente is None


def test_textos_de_hasta_y_rehabilita(persona):
    sancion = sancionar(persona, date(2026, 11, 2), date(2026, 11, 6))
    assert sancion.hasta == "viernes 6 de noviembre de 2026 a las 23:59"
    assert sancion.rehabilita == "sábado 7 de noviembre de 2026"
    assert sancion.periodo == "del 2 al 6 de noviembre"


# --- Fechas inválidas (decidido el 20/10: ni sin término ni con inicio futuro) ---

def test_no_se_permite_inicio_futuro(persona, hoy):
    sancion = Sancion(usuario=persona, inicio=hoy + timedelta(days=1), termino=hoy + timedelta(days=5), motivo="x")
    with pytest.raises(ValidationError) as error:
        sancion.full_clean()
    assert "inicio" in error.value.message_dict


def test_no_se_permite_sin_termino(persona, hoy):
    sancion = Sancion(usuario=persona, inicio=hoy, motivo="x")
    with pytest.raises(ValidationError) as error:
        sancion.full_clean()
    assert "termino" in error.value.message_dict


def test_no_se_permite_terminar_antes_de_empezar(persona, hoy):
    sancion = Sancion(usuario=persona, inicio=hoy, termino=hoy - timedelta(days=1), motivo="x")
    with pytest.raises(ValidationError) as error:
        sancion.full_clean()
    assert "termino" in error.value.message_dict


def test_la_base_tambien_rechaza_terminar_antes_de_empezar(persona, hoy):
    with pytest.raises(IntegrityError), transaction.atomic():
        sancionar(persona, hoy, hoy - timedelta(days=1))


def test_un_solo_dia_e_inicio_por_defecto_hoy(persona, hoy):
    sancion = Sancion(usuario=persona, termino=hoy, motivo="x")
    sancion.full_clean()
    assert sancion.inicio == hoy


# --- Administración de Django: solo el superusuario ---

@pytest.fixture
def superusuario():
    return Usuario.objects.create_superuser(email="root@uach.cl", password="x")


@pytest.fixture
def administrador():
    return Usuario.objects.create_user(email="admin@uach.cl", password="x", is_staff=True)


def test_superusuario_crea_sancion_y_queda_quien(client, superusuario, persona, hoy):
    client.force_login(superusuario)
    respuesta = client.post(reverse("admin:personas_sancion_add"), {
        "usuario": persona.pk,
        "motivo": "Dos inasistencias seguidas",
        "inicio": hoy.isoformat(),
        "termino": (hoy + timedelta(days=30)).isoformat(),
    })
    assert respuesta.status_code == 302, respuesta.context["adminform"].form.errors
    sancion = Sancion.objects.get()
    assert sancion.creada_por == superusuario
    assert sancion.usuario == persona


def test_administrador_no_superusuario_no_ve_sanciones_en_el_admin(client, administrador):
    client.force_login(administrador)
    assert client.get(reverse("admin:personas_sancion_changelist")).status_code == 403
    assert client.get(reverse("admin:personas_sancion_add")).status_code == 403


def test_en_el_admin_no_se_borra(client, superusuario, persona, hoy):
    sancion = sancionar(persona, hoy, hoy)
    client.force_login(superusuario)
    assert client.get(reverse("admin:personas_sancion_delete", args=[sancion.pk])).status_code == 403


# --- Pestaña Sanciones del panel: el administrador levanta ---

def test_panel_lista_solo_las_vigentes(client, administrador, persona, hoy):
    sancionar(persona, hoy, hoy + timedelta(days=5), motivo="Vigente de prueba")
    sancionar(persona, hoy - timedelta(days=20), hoy - timedelta(days=10), motivo="Pasada de prueba")
    client.force_login(administrador)
    respuesta = client.get(reverse("panel_sanciones"))
    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "Vigente de prueba" in contenido
    assert "Pasada de prueba" not in contenido


def test_panel_levanta_con_quien_cuando_y_motivo(client, administrador, persona, hoy):
    sancion = sancionar(persona, hoy, hoy + timedelta(days=5))
    client.force_login(administrador)
    respuesta = client.post(reverse("panel_sanciones"), {"sancion": sancion.pk, "motivo": "Presentó certificado"})
    assert respuesta.status_code == 302
    sancion.refresh_from_db()
    assert sancion.levantada_por == administrador
    assert sancion.levantada_en is not None
    assert sancion.motivo_levantamiento == "Presentó certificado"
    assert persona.sancion_vigente is None


def test_panel_no_levanta_sin_motivo(client, administrador, persona, hoy):
    sancion = sancionar(persona, hoy, hoy + timedelta(days=5))
    client.force_login(administrador)
    respuesta = client.post(reverse("panel_sanciones"), {"sancion": sancion.pk, "motivo": ""}, follow=True)
    assert "Escribe por qué se levanta la sanción." in respuesta.content.decode()
    sancion.refresh_from_db()
    assert sancion.levantada_en is None


def test_levantar_dos_veces_no_pisa_el_registro(administrador, persona, hoy):
    sancion = sancionar(persona, hoy, hoy + timedelta(days=5))
    services.levantar(sancion, administrador, "Primera")
    with pytest.raises(ValidationError):
        services.levantar(sancion, None, "Segunda")
    sancion.refresh_from_db()
    assert sancion.motivo_levantamiento == "Primera"
    assert sancion.levantada_por == administrador


def test_no_se_levanta_una_que_ya_termino(persona, hoy):
    sancion = sancionar(persona, hoy - timedelta(days=10), hoy - timedelta(days=1))
    with pytest.raises(ValidationError):
        services.levantar(sancion, None, "Tarde")


def test_el_solicitante_no_entra_al_panel(client, persona):
    client.force_login(persona)
    respuesta = client.get(reverse("panel_sanciones"))
    assert respuesta.status_code == 302
    assert reverse("login_gestion") in respuesta["Location"]
