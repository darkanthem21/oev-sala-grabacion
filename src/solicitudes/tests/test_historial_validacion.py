"""US-11: el historial de resoluciones del validador y del administrador, su
detalle de solo lectura y lo resuelto como solo lectura en /admin/."""
from datetime import date, datetime, timedelta
from itertools import count
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from agenda.models import Bloque, Dia, primera_fecha_pedible
from personas.models import Area, Rol, Usuario
from solicitudes.models import Acompanante, Solicitud, SolicitudBloque
from solicitudes.services import resolver
from solicitudes.views import RESOLUCIONES_POR_PAGINA

pytestmark = pytest.mark.django_db

SANTIAGO = ZoneInfo("America/Santiago")
URL = reverse("historial_validacion")


def a_las(dia, hora=10, minuto=0):
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=SANTIAGO)


def con_rol(usuario, rol):
    usuario.groups.add(Group.objects.get(name=rol))
    return usuario


@pytest.fixture
def informatica():
    return Area.objects.create(nombre="Informática", prioridad=1)


@pytest.fixture
def civil():
    return Area.objects.create(nombre="Civil", prioridad=2)


@pytest.fixture
def solicitante(informatica, civil):
    usuario = con_rol(Usuario.objects.create_user("docente@uach.cl", "x", first_name="Ana", last_name="Pérez"),
                      Rol.SOLICITANTE)
    usuario.areas.add(informatica, civil)
    return usuario


@pytest.fixture
def otra_solicitante(informatica):
    usuario = con_rol(Usuario.objects.create_user("otra@uach.cl", "x", first_name="Berta", last_name="Soto"),
                      Rol.SOLICITANTE)
    usuario.areas.add(informatica)
    return usuario


@pytest.fixture
def validador():
    return con_rol(Usuario.objects.create_user("valida@uach.cl", "x", first_name="Vale", last_name="Rojas"),
                   Rol.VALIDADOR)


@pytest.fixture
def otro_validador():
    return con_rol(Usuario.objects.create_user("valida2@uach.cl", "x", first_name="Víctor", last_name="Lagos"),
                   Rol.VALIDADOR)


@pytest.fixture
def administrador():
    return Usuario.objects.create_superuser("admin@uach.cl", "x")


@pytest.fixture
def jueves():
    """Un jueves pedible y sus dos primeros bloques."""
    minima = primera_fecha_pedible()
    fecha = minima + timedelta(days=(Dia.JUEVES - minima.weekday()) % 7)
    return fecha, list(Bloque.objects.filter(dia=Dia.JUEVES, activo=True).order_by("inicio")[:2])


def crear(usuario, area, jueves, numero_bloques=1, **campos):
    fecha, bloques = jueves
    solicitud = Solicitud.objects.create(solicitante=usuario, area=area, fecha=fecha, motivo="Grabar clase",
                                         **campos)
    for bloque in bloques[:numero_bloques]:
        SolicitudBloque.objects.create(solicitud=solicitud, bloque=bloque)
    return solicitud


_semanas = count(10)


def resuelta(usuario, area, jueves, quien, cuando, aprobada=True, motivo="", **campos):
    """Una solicitud ya resuelta en una fecha y hora dadas. Se crea pendiente y
    se resuelve con update(), como haría resolver(), para elegir `resuelta_en`.
    Cada una va en otro jueves: dos aprobadas no comparten bloque y fecha."""
    fecha, bloques = jueves
    solicitud = crear(usuario, area, (fecha + timedelta(weeks=next(_semanas)), bloques), **campos)
    estado = Solicitud.EstadoValidacion.ACEPTADA if aprobada else Solicitud.EstadoValidacion.RECHAZADA
    Solicitud.objects.filter(pk=solicitud.pk).update(
        estado_validacion=estado, motivo_resolucion=motivo, resuelta_por=quien, resuelta_en=cuando,
    )
    solicitud.refresh_from_db()
    return solicitud


def ids(respuesta):
    return [s.pk for s in respuesta.context["pagina"].object_list]


# --- T1: qué entra y en qué orden ---

def test_aparecen_las_resoluciones_de_todos_los_validadores_y_del_admin(
        client, solicitante, otra_solicitante, informatica, validador, otro_validador, administrador, jueves):
    del_validador = crear(solicitante, informatica, jueves)
    resolver(del_validador.pk, True, "", validador)
    del_otro = crear(otra_solicitante, informatica, (jueves[0] + timedelta(weeks=1), jueves[1]))
    resolver(del_otro.pk, False, "No hay técnico ese día", otro_validador)
    del_admin = resuelta(solicitante, informatica, jueves, administrador, a_las(date(2026, 9, 1)), aprobada=False,
                         motivo="Fuera de plazo")

    client.force_login(validador)
    respuesta = client.get(URL)

    assert respuesta.status_code == 200
    assert set(ids(respuesta)) == {del_validador.pk, del_otro.pk, del_admin.pk}
    contenido = respuesta.content.decode()
    for nombre in ("Vale Rojas", "Víctor Lagos", "admin@uach.cl"):
        assert nombre in contenido


def test_sin_pendientes_ni_retiradas(client, solicitante, informatica, validador, jueves):
    crear(solicitante, informatica, jueves)
    crear(solicitante, informatica, (jueves[0] + timedelta(weeks=1), jueves[1]),
          estado_validacion=Solicitud.EstadoValidacion.RETIRADA)
    lista = resuelta(solicitante, informatica, (jueves[0] + timedelta(weeks=2), jueves[1]), validador,
                     a_las(date(2026, 9, 1)))

    client.force_login(validador)
    assert ids(client.get(URL)) == [lista.pk]


def test_la_mas_reciente_primero(client, solicitante, informatica, validador, jueves):
    vieja = resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 8, 3)))
    nueva = resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 9, 3)))
    media = resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 8, 20)))

    client.force_login(validador)
    assert ids(client.get(URL)) == [nueva.pk, media.pk, vieja.pk]


def test_las_consultas_no_crecen_con_las_filas(
        client, solicitante, informatica, validador, jueves, django_assert_max_num_queries):
    client.force_login(validador)
    resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 9, 1)), numero_bloques=2)
    with django_assert_max_num_queries(20) as una:
        client.get(URL)
    for dia in range(2, 12):
        resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 9, dia)), numero_bloques=2)
    with django_assert_max_num_queries(len(una.captured_queries)):
        client.get(URL)


# --- T3: filtros ---

@pytest.fixture
def variedad(solicitante, informatica, civil, validador, otro_validador, jueves):
    """Una resolución de cada tipo, en días distintos."""
    return {
        "agosto_aprobada_informatica_v1": resuelta(solicitante, informatica, jueves, validador,
                                                   a_las(date(2026, 8, 10))),
        "septiembre_rechazada_civil_v2": resuelta(solicitante, civil, jueves, otro_validador,
                                                  a_las(date(2026, 9, 10)), aprobada=False, motivo="Sin técnico"),
        "octubre_rechazada_informatica_v1": resuelta(solicitante, informatica, jueves, validador,
                                                     a_las(date(2026, 10, 10)), aprobada=False, motivo="Choca"),
        "octubre_aprobada_civil_v2": resuelta(solicitante, civil, jueves, otro_validador,
                                              a_las(date(2026, 10, 12))),
    }


@pytest.mark.parametrize("filtro, esperadas", [
    ({"desde": "2026-09-10"}, {"septiembre_rechazada_civil_v2", "octubre_rechazada_informatica_v1",
                               "octubre_aprobada_civil_v2"}),
    ({"hasta": "2026-09-10"}, {"agosto_aprobada_informatica_v1", "septiembre_rechazada_civil_v2"}),
    ({"decision": "aprobada"}, {"agosto_aprobada_informatica_v1", "octubre_aprobada_civil_v2"}),
    ({"decision": "rechazada"}, {"septiembre_rechazada_civil_v2", "octubre_rechazada_informatica_v1"}),
])
def test_cada_filtro_solo(client, validador, variedad, filtro, esperadas):
    client.force_login(validador)
    assert set(ids(client.get(URL, filtro))) == {variedad[n].pk for n in esperadas}


def test_filtro_por_area(client, validador, variedad, civil):
    client.force_login(validador)
    assert set(ids(client.get(URL, {"area": civil.pk}))) == {
        variedad["septiembre_rechazada_civil_v2"].pk, variedad["octubre_aprobada_civil_v2"].pk}


def test_filtro_por_validador(client, validador, otro_validador, variedad):
    client.force_login(validador)
    assert set(ids(client.get(URL, {"validador": otro_validador.pk}))) == {
        variedad["septiembre_rechazada_civil_v2"].pk, variedad["octubre_aprobada_civil_v2"].pk}


def test_filtros_combinados(client, validador, variedad, informatica):
    client.force_login(validador)
    filtro = {"desde": "2026-09-01", "hasta": "2026-10-31", "area": informatica.pk,
              "decision": "rechazada", "validador": validador.pk}
    assert ids(client.get(URL, filtro)) == [variedad["octubre_rechazada_informatica_v1"].pk]


def test_la_fecha_es_la_de_santiago(client, solicitante, informatica, validador, jueves):
    """Resuelta a las 22:30 del 10 en Chile, ya es el 11 en UTC."""
    tarde = resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 9, 10), 22, 30))
    client.force_login(validador)
    assert ids(client.get(URL, {"desde": "2026-09-10", "hasta": "2026-09-10"})) == [tarde.pk]
    assert ids(client.get(URL, {"desde": "2026-09-11"})) == []


def test_desde_despues_de_hasta_avisa_y_no_filtra_esa_fecha(client, validador, variedad):
    client.force_login(validador)
    respuesta = client.get(URL, {"desde": "2026-10-01", "hasta": "2026-09-01"})
    assert "Tiene que ser igual o posterior" in respuesta.content.decode()
    assert set(ids(respuesta)) == {variedad["octubre_rechazada_informatica_v1"].pk,
                                   variedad["octubre_aprobada_civil_v2"].pk}


def test_solo_se_ofrecen_los_validadores_que_resolvieron_algo(client, validador, otro_validador, variedad):
    sin_nada = con_rol(Usuario.objects.create_user("nada@uach.cl", "x"), Rol.VALIDADOR)
    client.force_login(validador)
    opciones = client.get(URL).context["filtros"].fields["validador"].queryset
    assert set(opciones) == {validador, otro_validador}
    assert sin_nada not in opciones


def test_la_paginacion_conserva_los_filtros(client, solicitante, informatica, civil, validador, jueves):
    for dia in range(1, RESOLUCIONES_POR_PAGINA + 3):
        resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 8, dia)))
    resuelta(solicitante, civil, jueves, validador, a_las(date(2026, 9, 1)))
    client.force_login(validador)

    primera = client.get(URL, {"area": informatica.pk})
    enlace = f'{URL}?area={informatica.pk}&amp;pagina=2"'
    assert enlace in primera.content.decode()

    segunda = client.get(URL, {"area": informatica.pk, "pagina": 2})
    assert len(ids(segunda)) == 2
    assert all(s.area_id == informatica.pk for s in segunda.context["pagina"].object_list)


def test_htmx_recibe_solo_la_tabla(client, validador, variedad):
    client.force_login(validador)
    respuesta = client.get(URL, {"decision": "aprobada"}, headers={"HX-Request": "true"})
    nombres = [t.name for t in respuesta.templates]
    assert "solicitudes/_tabla_resoluciones.html" in nombres
    assert "solicitudes/historial_validacion.html" not in nombres
    assert "HX-Request" in respuesta["Vary"]


# --- T2: la tabla ---

def test_el_rechazo_por_tope_dice_a_quien_se_asigno(client, solicitante, otra_solicitante, informatica, validador,
                                                     jueves):
    ganadora = crear(solicitante, informatica, jueves)
    perdedora = crear(otra_solicitante, informatica, jueves)
    resolver(ganadora.pk, True, "Prioridad del área", validador)
    perdedora.refresh_from_db()
    assert perdedora.asignada_a_id == ganadora.pk

    client.force_login(validador)
    contenido = client.get(URL).content.decode()
    assert "asignada a" in contenido
    assert f'>#{ganadora.pk}</a></span>' in contenido
    assert "Prioridad del área" in contenido


def test_aprobada_sin_motivo_muestra_raya(client, solicitante, informatica, validador, jueves):
    """T6: hasta que la PO decida, una aprobada sin rivales no lleva motivo."""
    resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 9, 1)))
    client.force_login(validador)
    assert '<td data-titulo="Motivo">—</td>' in client.get(URL).content.decode()


def test_el_historial_no_tiene_acciones_que_cambien_datos(client, validador, variedad):
    client.force_login(validador)
    tabla = client.get(URL, headers={"HX-Request": "true"}).content.decode().lower()
    assert 'method="post"' not in tabla and "hx-post" not in tabla
    assert client.post(URL).status_code == 405
    assert Solicitud.objects.resueltas().count() == len(variedad)


# --- Acceso y envoltorio ---

def test_el_solicitante_no_entra(client, solicitante):
    client.force_login(solicitante)
    for url in (URL, reverse("historial_resolucion", args=[1])):
        respuesta = client.get(url)
        assert respuesta.status_code == 302
        assert reverse("login_validacion") in respuesta["Location"]


def test_sin_sesion_no_entra(client):
    assert client.get(URL).status_code == 302


def test_el_validador_lo_ve_con_su_encabezado(client, validador):
    client.force_login(validador)
    respuesta = client.get(URL)
    assert "solicitudes/_base_validador.html" in [t.name for t in respuesta.templates]
    assert f'href="{reverse("panel_validador")}"' in respuesta.content.decode()


def test_el_admin_lo_ve_en_su_pestana(client, administrador):
    client.force_login(administrador)
    respuesta = client.get(URL)
    assert respuesta.status_code == 200
    assert "panel.html" in [t.name for t in respuesta.templates]
    assert f'href="{reverse("panel_validacion")}"' in respuesta.content.decode()


@pytest.mark.parametrize("usuario, panel", [("validador", "panel_validador"), ("administrador", "panel_validacion")])
def test_los_paneles_enlazan_al_historial(client, request, usuario, panel):
    client.force_login(request.getfixturevalue(usuario))
    assert f'href="{URL}"' in client.get(reverse(panel)).content.decode()


# --- T4: el detalle ---

def test_el_detalle_muestra_lo_enviado_y_la_resolucion(client, solicitante, informatica, validador, jueves):
    solicitud = resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 9, 1), 15, 45),
                         aprobada=False, motivo="Sin técnico disponible", numero_bloques=2,
                         observaciones="Necesito micrófono de solapa", personas=2)
    Acompanante.objects.create(solicitud=solicitud, nombre="Carla Díaz", correo="carla@uach.cl")
    fecha, bloques = solicitud.fecha, jueves[1]

    client.force_login(validador)
    respuesta = client.get(reverse("historial_resolucion", args=[solicitud.pk]), {"area": informatica.pk})
    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    enviada = solicitud.creado_en.astimezone(SANTIAGO)
    for texto in ("Ana Pérez", "docente@uach.cl", "Informática", f"{fecha:%d/%m/%Y}",
                  f"{bloques[0].inicio:%H:%M}–{bloques[0].termino:%H:%M}",
                  f"{bloques[1].inicio:%H:%M}–{bloques[1].termino:%H:%M}",
                  "Grabar clase", "Necesito micrófono de solapa", "<dd>2</dd>", "Carla Díaz", "carla@uach.cl",
                  f"{enviada:%d/%m/%Y %H:%M}", "Rechazada", "Sin técnico disponible", "Vale Rojas",
                  "01/09/2026 15:45"):
        assert texto in contenido, texto
    # Volver lleva al historial con los mismos filtros.
    assert f'href="{URL}?area={informatica.pk}"' in contenido
    principal = contenido[contenido.index("<main"):].lower()
    assert 'method="post"' not in principal


def test_no_hay_detalle_de_una_pendiente(client, solicitante, informatica, validador, jueves):
    pendiente = crear(solicitante, informatica, jueves)
    client.force_login(validador)
    assert client.get(reverse("historial_resolucion", args=[pendiente.pk])).status_code == 404


# --- T5: /admin/ ---

@pytest.fixture
def resuelta_en_admin(solicitante, informatica, validador, jueves):
    solicitud = resuelta(solicitante, informatica, jueves, validador, a_las(date(2026, 9, 1)))
    Acompanante.objects.create(solicitud=solicitud, nombre="Carla Díaz", correo="carla@uach.cl")
    return solicitud


def test_admin_no_borra_una_resuelta(client, administrador, resuelta_en_admin):
    client.force_login(administrador)
    url = reverse("admin:solicitudes_solicitud_delete", args=[resuelta_en_admin.pk])
    assert client.get(url).status_code == 403
    assert client.post(url, {"post": "yes"}).status_code == 403
    assert Solicitud.objects.filter(pk=resuelta_en_admin.pk).exists()


def test_admin_no_la_borra_en_lote(client, administrador, resuelta_en_admin, solicitante, informatica, jueves):
    pendiente = crear(solicitante, informatica, (jueves[0] + timedelta(weeks=1), jueves[1]))
    client.force_login(administrador)
    client.post(reverse("admin:solicitudes_solicitud_changelist"), {
        "action": "delete_selected", "_selected_action": [resuelta_en_admin.pk, pendiente.pk], "post": "yes",
    })
    assert Solicitud.objects.filter(pk__in=[resuelta_en_admin.pk, pendiente.pk]).count() == 2


def test_admin_ve_la_resuelta_sin_poder_editarla(client, administrador, resuelta_en_admin):
    client.force_login(administrador)
    url = reverse("admin:solicitudes_solicitud_change", args=[resuelta_en_admin.pk])
    respuesta = client.get(url)
    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert 'name="_save"' not in contenido
    assert 'name="motivo"' not in contenido
    assert "Carla Díaz" in contenido
    assert 'name="acompanantes-0-nombre"' not in contenido
    assert 'name="solicitudes_bloques-0-bloque"' not in contenido

    assert client.post(url, {"motivo": "Cambiado"}).status_code == 403
    resuelta_en_admin.refresh_from_db()
    assert resuelta_en_admin.motivo == "Grabar clase"


def test_admin_no_toca_sus_bloques_ni_acompanantes_sueltos(client, administrador, resuelta_en_admin):
    client.force_login(administrador)
    bloque = resuelta_en_admin.solicitudes_bloques.get()
    acompanante = resuelta_en_admin.acompanantes.get()
    assert client.post(reverse("admin:solicitudes_solicitudbloque_delete", args=[bloque.pk]),
                       {"post": "yes"}).status_code == 403
    assert client.post(reverse("admin:solicitudes_acompanante_change", args=[acompanante.pk]),
                       {"nombre": "Otra", "correo": "otra@uach.cl", "solicitud": resuelta_en_admin.pk}
                       ).status_code == 403
    alta = client.get(reverse("admin:solicitudes_acompanante_add"))
    assert alta.context["adminform"].form.fields["solicitud"].queryset.filter(pk=resuelta_en_admin.pk).count() == 0
    assert SolicitudBloque.objects.filter(pk=bloque.pk).exists()
    acompanante.refresh_from_db()
    assert acompanante.nombre == "Carla Díaz"


def test_admin_aun_edita_y_borra_una_pendiente(client, administrador, solicitante, informatica, jueves):
    pendiente = crear(solicitante, informatica, jueves)
    client.force_login(administrador)
    assert 'name="_save"' in client.get(
        reverse("admin:solicitudes_solicitud_change", args=[pendiente.pk])).content.decode()
    client.post(reverse("admin:solicitudes_solicitud_delete", args=[pendiente.pk]), {"post": "yes"})
    assert not Solicitud.objects.filter(pk=pendiente.pk).exists()
