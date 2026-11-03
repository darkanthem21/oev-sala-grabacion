"""US-12: la pestaña Sanciones del administrador. Listado con conteos y
filtros, detalle de cada persona, aplicar y levantar."""
from datetime import date, datetime, time, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.urls import reverse

from agenda.models import Bloque, Dia
from configuracion.models import Parametros
from personas import services as personas
from personas.models import Area, Rol, Sancion, Usuario
from solicitudes.models import Solicitud, SolicitudBloque
from uso.checkout.models import Checkout, FormularioCheckout, FotoIntegridad
from uso.services import historial_personas

pytestmark = pytest.mark.django_db

SANTIAGO = ZoneInfo("America/Santiago")
HOY = date(2026, 11, 3)  # martes
LISTADO = reverse("panel_sanciones")

LISTADO_CHECKOUT = [
    {"id": "integridad", "titulo": "Estado e integridad", "preguntas": [
        {"id": "paredes", "texto": "¿Las paredes están sin daños?"},
        {"id": "puerta", "texto": "¿La puerta cierra bien?"},
    ]},
    {"id": "limpieza", "titulo": "Orden y limpieza", "preguntas": [
        {"id": "basura", "texto": "¿La sala está sin basura?"},
    ]},
]


def a_las(fecha, hora, minuto=0):
    return datetime(fecha.year, fecha.month, fecha.day, hora, minuto, tzinfo=SANTIAGO)


@pytest.fixture(autouse=True)
def hoy_fijo():
    with mock.patch("django.utils.timezone.now", return_value=a_las(HOY, 10)):
        yield


@pytest.fixture
def informatica():
    return Area.objects.create(nombre="Informática")


@pytest.fixture
def civil():
    return Area.objects.create(nombre="Civil")


def solicitante(correo, *areas, nombre=""):
    usuario = Usuario.objects.create_user(email=correo, password="x", first_name=nombre)
    usuario.groups.add(Group.objects.get(name=Rol.SOLICITANTE))
    usuario.areas.add(*areas)
    return usuario


@pytest.fixture
def ana(informatica, civil):
    """En dos áreas, para ver que filtrar por una no la duplica."""
    return solicitante("ana@uach.cl", informatica, civil, nombre="Ana")


@pytest.fixture
def beto(informatica):
    return solicitante("beto@uach.cl", informatica, nombre="Beto")


@pytest.fixture
def administrador():
    return Usuario.objects.create_user(email="admin@uach.cl", password="x", is_staff=True)


@pytest.fixture
def bloque():
    return Bloque.objects.create(dia=Dia.LUNES, inicio=time(9), termino=time(10, 30))


def reserva(persona, area, fecha, bloque, **estado):
    campos = {"estado_validacion": Solicitud.EstadoValidacion.ACEPTADA,
              "estado_confirmacion": Solicitud.EstadoConfirmacion.CONFIRMADA, **estado}
    solicitud = Solicitud.objects.create(solicitante=persona, area=area, fecha=fecha, motivo="Grabación", **campos)
    # bulk_create no pasa por SolicitudBloque.save(), que revisaría el día y si
    # el bloque está libre: acá se arma historia, no se pide la sala.
    SolicitudBloque.objects.bulk_create([SolicitudBloque(solicitud=solicitud, bloque=bloque)])
    return solicitud


def checkout(persona, area, fecha, bloque, noes=(), observacion="Quedó un panel suelto en la pared"):
    """Un check-out con «No» en las preguntas de `noes`, y su foto por cada una,
    como lo deja US-20."""
    ticket = reserva(persona, area, fecha, bloque).solicitudes_bloques.get()
    respuestas = {p["id"]: {"cumple": p["id"] not in noes, "observacion": observacion if p["id"] in noes else ""}
                  for s in LISTADO_CHECKOUT for p in s["preguntas"]}
    registro = Checkout.objects.create(ticket=ticket, formulario=LISTADO_CHECKOUT, revision=1, respuestas=respuestas,
                                       hora_salida=time(10, 30), observaciones="")
    for clave in noes:
        FotoIntegridad.objects.create(checkout=registro, pregunta=clave, archivo=f"checkout/{clave}.jpg")
    return registro


def filas(respuesta):
    return [(p.email, p.incidentes) for p in respuesta.context["pagina"].object_list]


def entrar(client, usuario):
    client.force_login(usuario)
    return client


# --- Inasistencias: la regla de US-03 en SQL ---

def test_que_cuenta_como_inasistencia(ana, informatica, bloque):
    ayer, manana = HOY - timedelta(days=1), HOY + timedelta(days=1)
    lunes = date(2026, 11, 2)
    no_confirmada = reserva(ana, informatica, ayer, bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.PENDIENTE)
    reserva(ana, informatica, ayer, bloque)  # confirmada: se usó
    reserva(ana, informatica, manana, bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.NO_HABILITADA)
    cancelada_tarde = reserva(ana, informatica, manana, bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.CANCELADA,
                              cancelada_en=a_las(lunes, 0, 5))
    reserva(ana, informatica, manana, bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.CANCELADA,
            cancelada_en=a_las(lunes - timedelta(days=1), 23, 55))  # el domingo antes: a tiempo
    reserva(ana, informatica, ayer, bloque, estado_validacion=Solicitud.EstadoValidacion.RECHAZADA)
    assert set(Solicitud.objects.inasistencias()) == {no_confirmada, cancelada_tarde}
    # Y coincide con lo que dice cada solicitud por su cuenta.
    for s in Solicitud.objects.all():
        cuenta = s.estado_clave == "no-confirmada" or (s.estado_clave == "cancelada" and s.cancelar_cuenta_inasistencia)
        assert (s in {no_confirmada, cancelada_tarde}) == cuenta, s


# --- Listado (T3, T4) ---

def test_cuenta_incidentes_e_inasistencias_por_persona(client, administrador, ana, beto, informatica, bloque):
    checkout(ana, informatica, date(2026, 10, 5), bloque, noes=["paredes", "basura"])
    checkout(ana, informatica, date(2026, 10, 12), bloque, noes=["puerta"])
    checkout(beto, informatica, date(2026, 10, 6), bloque)  # todo «Sí»: no es incidente
    reserva(beto, informatica, date(2026, 10, 7), bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.PENDIENTE)
    respuesta = entrar(client, administrador).get(LISTADO)
    assert respuesta.status_code == 200
    datos = {p.email: (p.incidentes, p.inasistencias) for p in respuesta.context["pagina"].object_list}
    assert datos == {"ana@uach.cl": (3, 0), "beto@uach.cl": (0, 1)}


def test_orden_mas_incidentes_primero_y_luego_id(client, administrador, informatica, bloque):
    primeros = [solicitante(f"p{i}@uach.cl", informatica) for i in range(3)]
    checkout(primeros[2], informatica, date(2026, 10, 5), bloque, noes=["paredes"])
    respuesta = entrar(client, administrador).get(LISTADO)
    assert [e for e, _ in filas(respuesta)] == ["p2@uach.cl", "p0@uach.cl", "p1@uach.cl"]


def test_filtrar_por_area_no_duplica_ni_infla(client, administrador, ana, beto, informatica, civil, bloque):
    checkout(ana, informatica, date(2026, 10, 5), bloque, noes=["paredes", "puerta", "basura"])
    entrar(client, administrador)
    assert filas(client.get(LISTADO)) == [("ana@uach.cl", 3), ("beto@uach.cl", 0)]
    assert filas(client.get(LISTADO, {"area": informatica.pk})) == [("ana@uach.cl", 3), ("beto@uach.cl", 0)]
    assert filas(client.get(LISTADO, {"area": civil.pk})) == [("ana@uach.cl", 3)]
    assert client.get(LISTADO, {"area": civil.pk}).context["pagina"].paginator.count == 1


@pytest.fixture
def cuatro_estados(administrador, informatica):
    vigente = solicitante("vigente@uach.cl", informatica)
    Sancion.objects.create(usuario=vigente, motivo="Vigente de prueba", inicio=HOY, termino=HOY + timedelta(days=5))
    levantada = solicitante("levantada@uach.cl", informatica)
    s = Sancion.objects.create(usuario=levantada, motivo="x", inicio=HOY, termino=HOY + timedelta(days=5))
    personas.levantar(s, administrador, "Justificó")
    terminada = solicitante("terminada@uach.cl", informatica)
    Sancion.objects.create(usuario=terminada, motivo="Pasada de prueba", inicio=date(2026, 9, 1), termino=date(2026, 9, 30))
    solicitante("sin@uach.cl", informatica)


@pytest.mark.parametrize("estado", ["vigente", "levantada", "terminada", "sin"])
def test_filtro_por_estado_de_la_sancion(client, administrador, cuatro_estados, estado):
    respuesta = entrar(client, administrador).get(LISTADO, {"estado": estado})
    assert [e for e, _ in filas(respuesta)] == [f"{estado}@uach.cl"]


def test_la_vigente_manda_sobre_una_levantada_mas_nueva(administrador, informatica):
    persona = solicitante("doble@uach.cl", informatica)
    Sancion.objects.create(usuario=persona, motivo="larga", inicio=HOY - timedelta(days=5), termino=HOY + timedelta(days=20))
    corta = Sancion.objects.create(usuario=persona, motivo="corta", inicio=HOY, termino=HOY + timedelta(days=1))
    personas.levantar(corta, administrador, "x")
    fila = historial_personas().get(pk=persona.pk)
    assert (fila.estado_sancion, fila.vigente_motivo) == ("vigente", "larga")


def test_la_fila_vigente_dice_hasta_cuando_y_por_que(client, administrador, cuatro_estados):
    contenido = entrar(client, administrador).get(LISTADO).content.decode()
    assert "Vigente de prueba" in contenido
    assert "hasta el 08/11/2026" in contenido
    assert "Pasada de prueba" not in contenido  # eso va en el detalle


def test_filtro_por_texto(client, administrador, ana, beto):
    assert [e for e, _ in filas(entrar(client, administrador).get(LISTADO, {"texto": "BETO"}))] == ["beto@uach.cl"]


def test_filtro_mal_escrito_se_ignora(client, administrador, ana, beto):
    respuesta = entrar(client, administrador).get(LISTADO, {"estado": "otro", "area": "999"})
    assert len(filas(respuesta)) == 2
    assert respuesta.context["filtros"].errors


def test_quien_no_pide_ni_fue_sancionado_no_aparece(client, administrador, ana):
    respuesta = entrar(client, administrador).get(LISTADO)
    assert [e for e, _ in filas(respuesta)] == ["ana@uach.cl"]


def test_el_numero_de_consultas_es_fijo(client, administrador, informatica, civil, bloque, django_assert_num_queries):
    """Sesión, usuario, el área del filtro, el COUNT del paginador, Parametros,
    la página entera (conteos, sanción y áreas como subconsultas) y las
    opciones del filtro de área. Ni una más por fila."""
    entrar(client, administrador)
    Parametros.cargar()  # la primera vez la crea, y eso no es del listado
    for i in range(3):
        persona = solicitante(f"a{i}@uach.cl", informatica, civil)
        checkout(persona, informatica, date(2026, 10, 1 + i), bloque, noes=["paredes"])
    with django_assert_num_queries(7):
        client.get(LISTADO, {"area": informatica.pk})
    for i in range(20):
        persona = solicitante(f"b{i}@uach.cl", informatica)
        Sancion.objects.create(usuario=persona, motivo="x", inicio=HOY, termino=HOY)
        checkout(persona, informatica, date(2026, 9, 1 + i), bloque, noes=["puerta", "basura"])
    with django_assert_num_queries(7):
        client.get(LISTADO, {"area": informatica.pk})


def test_htmx_recibe_solo_la_tabla(client, administrador, ana):
    respuesta = entrar(client, administrador).get(LISTADO, HTTP_HX_REQUEST="true")
    contenido = respuesta.content.decode()
    assert 'id="personas"' in contenido
    assert "<html" not in contenido
    assert "HX-Request" in respuesta["Vary"]


def test_paginas_de_25(client, administrador, informatica):
    for i in range(27):
        solicitante(f"p{i:02d}@uach.cl", informatica)
    entrar(client, administrador)
    assert len(filas(client.get(LISTADO))) == 25
    assert len(filas(client.get(LISTADO, {"pagina": 2}))) == 2


def test_marca_a_quien_llega_al_umbral_de_reglas(client, administrador, ana, beto, informatica, bloque):
    parametros = Parametros.cargar()
    parametros.inasistencias_para_sancion = 2
    parametros.save()
    for dia in (5, 12):
        reserva(ana, informatica, date(2026, 10, dia), bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.PENDIENTE)
    reserva(beto, informatica, date(2026, 10, 5), bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.PENDIENTE)
    entrar(client, administrador)
    contenido = client.get(LISTADO).content.decode()
    assert contenido.count("Llega al umbral de 2") == 1
    # Sancionada después de esas dos, ya no se marca.
    Sancion.objects.create(usuario=ana, motivo="x", inicio=date(2026, 10, 20), termino=date(2026, 10, 25))
    assert "Llega al umbral" not in client.get(LISTADO).content.decode()


# --- Permisos ---

@pytest.mark.parametrize("url", [LISTADO, "/configuracion/sanciones/1/"])
def test_solo_el_administrador(client, ana, url):
    for quien in (None, ana):
        client.logout()
        if quien:
            client.force_login(quien)
        respuesta = client.get(url)
        assert respuesta.status_code == 302
        assert reverse("login_gestion") in respuesta["Location"]
    assert client.post(reverse("sanciones_de", args=[ana.pk]), {"accion": "aplicar", "motivo": "x"}).status_code == 302
    assert not Sancion.objects.exists()


def test_detalle_de_alguien_que_no_existe_es_404(client, administrador):
    assert entrar(client, administrador).get(reverse("sanciones_de", args=[999999])).status_code == 404


# --- Detalle (T5) ---

def test_detalle_con_la_pregunta_y_la_observacion_de_ese_check_out(client, administrador, ana, informatica, bloque):
    checkout(ana, informatica, date(2026, 10, 5), bloque, noes=["paredes"])
    # El administrador cambió el listado después: se ve lo que se preguntó entonces.
    listado = FormularioCheckout.cargar()
    listado.secciones = [{"id": "x", "titulo": "Otra", "preguntas": [{"id": "paredes", "texto": "Texto nuevo"}]}]
    listado.save()
    contenido = entrar(client, administrador).get(reverse("sanciones_de", args=[ana.pk])).content.decode()
    assert "¿Las paredes están sin daños?" in contenido
    assert "Texto nuevo" not in contenido
    assert "Quedó un panel suelto en la pared" in contenido
    assert "09:00–10:30" in contenido
    assert "Estado e integridad" in contenido


def test_detalle_en_orden_cronologico(client, administrador, ana, informatica, bloque):
    checkout(ana, informatica, date(2026, 10, 12), bloque, noes=["basura"])
    reserva(ana, informatica, date(2026, 10, 5), bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.PENDIENTE)
    sancion = Sancion.objects.create(usuario=ana, motivo="Dos faltas", inicio=date(2026, 10, 20), termino=date(2026, 10, 25),
                                     creada_por=administrador)
    personas.levantar(Sancion.objects.create(usuario=ana, motivo="Otra", inicio=HOY, termino=HOY + timedelta(days=3)),
                      administrador, "Presentó certificado")
    respuesta = entrar(client, administrador).get(reverse("sanciones_de", args=[ana.pk]))
    eventos = respuesta.context["eventos"]
    assert [(e["tipo"], e["fecha"]) for e in eventos] == [
        ("inasistencia", date(2026, 10, 5)), ("incidente", date(2026, 10, 12)),
        ("sancion", date(2026, 10, 20)), ("sancion", HOY),
    ]
    assert eventos[2]["sancion"] == sancion and eventos[2]["estado"] == "terminada"
    contenido = respuesta.content.decode()
    assert "Puesta por admin@uach.cl" in contenido
    assert "Presentó certificado" in contenido


def test_detalle_con_un_numero_fijo_de_consultas(client, administrador, ana, informatica, bloque,
                                                 django_assert_max_num_queries):
    entrar(client, administrador)
    checkout(ana, informatica, date(2026, 10, 1), bloque, noes=["paredes"])
    url = reverse("sanciones_de", args=[ana.pk])
    with django_assert_max_num_queries(20) as una:
        client.get(url)
    for dia in range(2, 12):
        checkout(ana, informatica, date(2026, 10, dia), bloque, noes=["paredes", "puerta"])
        reserva(ana, informatica, date(2026, 9, dia), bloque, estado_confirmacion=Solicitud.EstadoConfirmacion.PENDIENTE)
    with django_assert_max_num_queries(len(una.captured_queries)):
        client.get(url)


# --- Aplicar desde el detalle (T6, T8) ---

def test_aplicar_con_las_fechas_propuestas(client, administrador, ana, django_capture_on_commit_callbacks):
    entrar(client, administrador)
    url = reverse("sanciones_de", args=[ana.pk])
    formulario = client.get(url).context["aplicar"]
    assert formulario.initial == {"inicio": HOY, "termino": date(2026, 12, 2)}
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = client.post(url, {"accion": "aplicar", "motivo": "Dos inasistencias", "inicio": "2026-11-03",
                                      "termino": "2026-12-02", "volver": "estado=sin"}, follow=True)
    assert respuesta.redirect_chain[-1][0] == f"{url}?estado=sin"
    sancion = Sancion.objects.get()
    assert (sancion.usuario, sancion.creada_por, sancion.motivo) == (ana, administrador, "Dos inasistencias")
    assert "Sancionaste a Ana del 3 de noviembre al 2 de diciembre" in respuesta.content.decode()
    assert mail.outbox[0].to == ["ana@uach.cl"]


@pytest.mark.parametrize("datos, error", [
    ({"motivo": "", "inicio": "2026-11-03", "termino": "2026-11-05"}, "Escribe el motivo de la sanción"),
    ({"motivo": "x", "inicio": "2026-11-04", "termino": "2026-11-05"}, "no puede empezar en una fecha futura"),
    ({"motivo": "x", "inicio": "2026-11-03", "termino": "2026-11-02"}, "tiene que terminar el mismo día"),
    ({"motivo": "x", "inicio": "2026-11-01", "termino": "2026-11-04"}, "Se cruza con otra sanción"),
])
def test_aplicar_mal_vuelve_con_el_error(client, administrador, ana, datos, error):
    Sancion.objects.create(usuario=ana, motivo="vieja", inicio=date(2026, 10, 20), termino=date(2026, 11, 1))
    respuesta = entrar(client, administrador).post(reverse("sanciones_de", args=[ana.pk]), {"accion": "aplicar", **datos})
    assert respuesta.status_code == 200
    assert error in respuesta.content.decode()
    assert Sancion.objects.count() == 1
    assert not mail.outbox


def test_accion_desconocida_es_400(client, administrador, ana):
    assert entrar(client, administrador).post(reverse("sanciones_de", args=[ana.pk]), {"accion": "x"}).status_code == 400


# --- Levantar (T7) ---

def test_levantar_desde_el_detalle_vuelve_al_detalle(client, administrador, ana):
    sancion = Sancion.objects.create(usuario=ana, motivo="x", inicio=HOY, termino=HOY + timedelta(days=5))
    url = reverse("sanciones_de", args=[ana.pk])
    respuesta = entrar(client, administrador).post(url, {"accion": "levantar", "sancion": sancion.pk,
                                                         "motivo": "Presentó certificado"}, follow=True)
    assert respuesta.redirect_chain[-1][0] == url
    assert "Levantaste la sanción de Ana. Ya puede solicitar la sala." in respuesta.content.decode()
    sancion.refresh_from_db()
    assert (sancion.levantada_por, sancion.motivo_levantamiento) == (administrador, "Presentó certificado")


def test_con_otra_vigente_el_aviso_no_promete_que_ya_puede(client, administrador, ana):
    corta = Sancion.objects.create(usuario=ana, motivo="corta", inicio=HOY, termino=HOY + timedelta(days=2))
    Sancion.objects.create(usuario=ana, motivo="larga", inicio=HOY - timedelta(days=1), termino=HOY + timedelta(days=9))
    respuesta = entrar(client, administrador).post(LISTADO, {"sancion": corta.pk, "motivo": "Se justificó"}, follow=True)
    contenido = respuesta.content.decode()
    assert "Ya puede solicitar la sala" not in contenido
    assert "tiene otra vigente: sigue sin poder solicitar la sala hasta el jueves 12 de noviembre de 2026 a las 23:59" in contenido
    assert ana.sancion_vigente.motivo == "larga"


def test_levantar_desde_el_listado_conserva_los_filtros(client, administrador, ana):
    sancion = Sancion.objects.create(usuario=ana, motivo="x", inicio=HOY, termino=HOY)
    respuesta = entrar(client, administrador).post(LISTADO, {"sancion": sancion.pk, "motivo": "x",
                                                             "volver": "estado=vigente&pagina=1"})
    assert respuesta["Location"] == f"{LISTADO}?estado=vigente&pagina=1"


# --- De punta a punta: bloqueado y luego habilitado ---

def test_aplicar_bloquea_al_solicitante_y_levantar_lo_habilita(client, administrador, ana):
    url = reverse("sanciones_de", args=[ana.pk])
    entrar(client, administrador).post(url, {"accion": "aplicar", "motivo": "Dos inasistencias",
                                             "inicio": "2026-11-03", "termino": "2026-11-10"})
    client.force_login(ana)
    assert "No puedes solicitar por ahora" in client.get(reverse("solicitar"), follow=True).content.decode()
    client.force_login(administrador)
    client.post(url, {"accion": "levantar", "sancion": Sancion.objects.get().pk, "motivo": "Se justificó"})
    client.force_login(ana)
    assert "No puedes solicitar por ahora" not in client.get(reverse("solicitar"), follow=True).content.decode()
