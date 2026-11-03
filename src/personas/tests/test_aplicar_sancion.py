"""US-12: aplicar una sanción desde el servicio, con sus reglas, su correo y el
bloqueo que impide que dos administradores a la vez la crucen."""
import threading
import time
from datetime import date, datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from configuracion.models import Parametros
from personas import services
from personas.models import Sancion, Usuario

pytestmark = pytest.mark.django_db

SANTIAGO = ZoneInfo("America/Santiago")
# Un martes. Todas las fechas de este archivo cuelgan de él.
HOY = date(2026, 11, 3)


def a_las(fecha, hora, minuto=0):
    return datetime(fecha.year, fecha.month, fecha.day, hora, minuto, tzinfo=SANTIAGO)


@pytest.fixture(autouse=True)
def hoy_fijo():
    with mock.patch("django.utils.timezone.now", return_value=a_las(HOY, 10)):
        yield


@pytest.fixture
def persona():
    return Usuario.objects.create_user(email="docente@uach.cl", password="x", first_name="Ana", last_name="Soto")


@pytest.fixture
def administrador():
    return Usuario.objects.create_user(email="admin@uach.cl", password="x", is_staff=True)


def con_dias(dias):
    parametros = Parametros.cargar()
    parametros.dias_sancion = dias
    parametros.save()


# --- Fechas por defecto: el día de término cuenta entero ---

def test_por_defecto_empieza_hoy_y_dura_dias_sancion_contando_el_primero(persona, administrador):
    """30 días desde el 3/11 son del 3/11 al 2/12: el 2/12 rige hasta las 23:59
    y el 3/12 ya se puede pedir. inicio + 30 sería un día de más."""
    con_dias(30)
    sancion = services.aplicar(persona, "Dos inasistencias", administrador)
    assert sancion.inicio == HOY
    assert sancion.termino == date(2026, 12, 2)
    assert (sancion.termino - sancion.inicio).days + 1 == 30
    assert sancion.rehabilita == "jueves 3 de diciembre de 2026"


def test_la_duracion_sale_de_reglas_y_no_del_codigo(persona):
    con_dias(7)
    assert services.aplicar(persona, "x", None).termino == date(2026, 11, 9)


def test_un_dia_termina_el_mismo_dia_y_rige_hasta_las_23_59(persona):
    con_dias(1)
    sancion = services.aplicar(persona, "Llegó tarde", None)
    assert sancion.termino == HOY
    with mock.patch("django.utils.timezone.now", return_value=a_las(HOY, 23, 59)):
        assert persona.sancion_vigente == sancion
    with mock.patch("django.utils.timezone.now", return_value=a_las(HOY + timedelta(days=1), 0, 0)):
        assert persona.sancion_vigente is None


def test_termino_por_defecto_desde_otro_inicio():
    assert services.termino_por_defecto(date(2026, 2, 1), 28) == date(2026, 2, 28)


def test_queda_quien_y_cuando(persona, administrador):
    sancion = services.aplicar(persona, "x", administrador)
    sancion.refresh_from_db()
    assert sancion.creada_por == administrador
    assert sancion.creada_en == a_las(HOY, 10)


def test_fechas_elegidas_a_mano(persona):
    sancion = services.aplicar(persona, "x", None, inicio=HOY - timedelta(days=2), termino=HOY + timedelta(days=3))
    assert (sancion.inicio, sancion.termino) == (date(2026, 11, 1), date(2026, 11, 6))


# --- Lo que no se acepta ---

@pytest.mark.parametrize("motivo", ["", "   ", None])
def test_sin_motivo_no(persona, motivo):
    with pytest.raises(ValidationError) as error:
        services.aplicar(persona, motivo, None)
    assert "motivo" in error.value.message_dict
    assert not Sancion.objects.exists()


def test_termino_antes_del_inicio_no(persona):
    with pytest.raises(ValidationError) as error:
        services.aplicar(persona, "x", None, inicio=HOY, termino=HOY - timedelta(days=1))
    assert "termino" in error.value.message_dict


def test_inicio_futuro_no(persona):
    """US-10, decidido el 20/10: no se sanciona por adelantado."""
    with pytest.raises(ValidationError) as error:
        services.aplicar(persona, "x", None, inicio=HOY + timedelta(days=1))
    assert "inicio" in error.value.message_dict


# --- Sin cruces con otra no levantada ---

def test_no_se_cruza_con_una_vigente(persona):
    services.aplicar(persona, "Primera", None, termino=HOY + timedelta(days=5))
    with pytest.raises(ValidationError) as error:
        services.aplicar(persona, "Segunda", None, inicio=HOY - timedelta(days=3), termino=HOY)
    assert "Se cruza con otra sanción" in " ".join(error.value.messages)
    assert Sancion.objects.count() == 1


def test_compartir_un_solo_dia_ya_es_cruce(persona):
    """Los dos extremos cuentan enteros: terminar el día que otra empieza la pisa."""
    Sancion.objects.create(usuario=persona, motivo="vieja", inicio=date(2026, 10, 1), termino=date(2026, 10, 20))
    with pytest.raises(ValidationError):
        services.aplicar(persona, "x", None, inicio=date(2026, 10, 20), termino=date(2026, 10, 25))
    services.aplicar(persona, "x", None, inicio=date(2026, 10, 21), termino=date(2026, 10, 25))


def test_una_terminada_sin_levantar_tambien_cuenta(persona):
    Sancion.objects.create(usuario=persona, motivo="vieja", inicio=date(2026, 10, 1), termino=date(2026, 10, 20))
    with pytest.raises(ValidationError):
        services.aplicar(persona, "x", None, inicio=date(2026, 10, 15))


def test_una_levantada_no_cuenta(persona, administrador):
    vigente = services.aplicar(persona, "Primera", administrador)
    services.levantar(vigente, administrador, "Se justificó")
    nueva = services.aplicar(persona, "Segunda", administrador)
    assert persona.sancion_vigente == nueva


def test_la_de_otra_persona_no_cuenta(persona):
    otra = Usuario.objects.create_user(email="otra@uach.cl", password="x")
    services.aplicar(otra, "x", None)
    services.aplicar(persona, "x", None)


def test_el_admin_de_django_tampoco_las_cruza(client, persona):
    """La regla vive en Sancion.clean(), así que /admin/ también la cumple."""
    raiz = Usuario.objects.create_superuser(email="root@uach.cl", password="x")
    services.aplicar(persona, "Primera", None)
    client.force_login(raiz)
    respuesta = client.post(reverse("admin:personas_sancion_add"), {
        "usuario": persona.pk, "motivo": "Segunda", "inicio": HOY.isoformat(),
        "termino": (HOY + timedelta(days=2)).isoformat(),
    })
    assert respuesta.status_code == 200
    assert "Se cruza con otra sanción" in respuesta.content.decode()
    assert Sancion.objects.count() == 1


def test_acortar_en_el_admin_no_choca_consigo_misma(persona):
    sancion = services.aplicar(persona, "x", None)
    sancion.termino = HOY + timedelta(days=2)
    sancion.full_clean()


# --- Concurrencia ---

def test_bloquea_la_fila_de_la_persona_antes_de_revisar(persona):
    with CaptureQueriesContext(connection) as consultas:
        services.aplicar(persona, "x", None)
    sql = [c["sql"] for c in consultas.captured_queries]
    bloqueo = next(i for i, s in enumerate(sql) if "FOR UPDATE" in s)
    assert '"personas_usuario"' in sql[bloqueo]
    cruce = next(i for i, s in enumerate(sql) if '"personas_sancion"' in s and "SELECT" in s)
    assert bloqueo < cruce


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_dos_administradores_a_la_vez_dejan_una_sola(persona):
    """Sin el bloqueo, los dos revisarían el cruce antes de que el otro guarde
    y quedarían dos sanciones pisadas. La pausa después de full_clean() abre esa
    ventana a propósito."""
    Parametros.cargar()
    original = Sancion.full_clean
    barrera = threading.Barrier(2)
    resultados = []

    def lento(self, *args, **kwargs):
        original(self, *args, **kwargs)
        time.sleep(0.4)

    def sancionar(motivo):
        try:
            barrera.wait()
            services.aplicar(persona, motivo, None)
            resultados.append("guardada")
        except ValidationError:
            resultados.append("rechazada")
        finally:
            connection.close()

    with mock.patch.object(Sancion, "full_clean", lento):
        hilos = [threading.Thread(target=sancionar, args=(m,)) for m in ("Primera", "Segunda")]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(10)
    assert sorted(resultados) == ["guardada", "rechazada"]
    assert Sancion.objects.filter(usuario=persona).count() == 1


# --- Aviso por correo ---

def test_avisa_por_correo_al_confirmarse(persona, administrador, django_capture_on_commit_callbacks):
    con_dias(30)
    with django_capture_on_commit_callbacks(execute=True) as pendientes:
        services.aplicar(persona, "Dos inasistencias sin aviso", administrador)
        assert not mail.outbox, "no sale antes del commit"
    assert len(pendientes) == 1
    assert len(mail.outbox) == 1
    correo = mail.outbox[0]
    assert correo.to == ["docente@uach.cl"]
    assert "Ana Soto" in correo.body
    assert "Dos inasistencias sin aviso" in correo.body
    assert "del 3 de noviembre al 2 de diciembre" in correo.body
    assert "miércoles 2 de diciembre de 2026 a las 23:59" in correo.body
    assert "jueves 3 de diciembre de 2026" in correo.body


def test_sin_sancion_no_hay_correo(persona, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(ValidationError):
        services.aplicar(persona, "", None)
    assert not mail.outbox
