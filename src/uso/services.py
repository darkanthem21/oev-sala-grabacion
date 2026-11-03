"""US-14: qué bloques ve el personal de apoyo.

Cada bloque de la lista es un ticket: un bloque de una solicitud aceptada en una
fecha (`SolicitudBloque`). El estado de completado se lee de `Checkout` y es
compartido por todo el personal de apoyo.

AC7 quedó decidido así: todos los del personal de apoyo ven todos los bloques del
día. Es el supuesto del equipo ("siempre hay personal de apoyo, no se modela su
disponibilidad") y el modelo de datos no tiene a quién asignarlos.
"""
from datetime import date, datetime

from django.contrib.auth.models import Group
from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from agenda.models import bloqueos_por_fecha
from personas.models import Area, Rol, Sancion, Usuario
from solicitudes.models import Solicitud, SolicitudBloque
from .checkout.models import Checkout, FotoIntegridad

# AC4: solo las aceptadas; una pendiente todavía puede rechazarse, así que no
# hay a quién esperar. AC5: la cancelada se lista marcada en vez de desaparecer,
# para que nadie se quede esperando a alguien que ya avisó que no viene.
ESTADOS = {
    Solicitud.EstadoConfirmacion.NO_HABILITADA: "aprobada",
    Solicitud.EstadoConfirmacion.PENDIENTE: "aprobada",
    Solicitud.EstadoConfirmacion.CONFIRMADA: "confirmada",
    Solicitud.EstadoConfirmacion.CANCELADA: "cancelada",
}


def _estado(solicitud):
    # US-03: la que llegó a su día sin confirmar tampoco se espera. Lo calcula
    # estado_clave por la fecha; la fila sigue aceptada.
    if solicitud.estado_clave == "no-confirmada":
        return "no confirmada"
    return ESTADOS[solicitud.estado_confirmacion]


def _tickets(**filtro):
    filas = SolicitudBloque.objects.filter(
        solicitud__estado_validacion=Solicitud.EstadoValidacion.ACEPTADA, **filtro
    ).select_related("bloque", "solicitud__solicitante", "solicitud__area")
    return [
        {
            "ticket": f.ticket,
            "bloque_id": f.bloque_id,
            "fecha": f.fecha,
            "inicio": f.inicio,
            "termino": f.termino,
            "solicitante": f.solicitud.solicitante.get_full_name() or f.solicitud.solicitante.email,
            "area": f.solicitud.area.nombre,
            "personas": f.solicitud.personas,
            "estado": _estado(f.solicitud),
        }
        for f in filas
    ]


def _armar(t, enviados, ahora):
    """El ticket con su estado de check-out resuelto (AC6).

    `checkout` es "completado", "pendiente" si el bloque ya terminó y le falta, o
    None si todavía no termina, se canceló o no se confirmó: en esos casos no
    hay nada que revisar en la sala.
    """
    termino_en = timezone.make_aware(datetime.combine(t["fecha"], t["termino"]))
    if t["ticket"] in enviados:
        checkout = "completado"
    elif t["estado"] not in ("cancelada", "no confirmada") and termino_en <= ahora:
        checkout = "pendiente"
    else:
        checkout = None
    return {**t, "checkout": checkout}


def bloques_del_dia(fecha, enviados=None, ahora=None):
    """Los bloques de esa fecha que le importan al personal de apoyo.

    `enviados` permite indicar códigos explícitos; por defecto se leen de la base.
    Cada bloque trae además el bloqueo que le quitó la sala, si hay uno (US-17
    AC2), para que nadie la prepare para una grabación que no va a ocurrir.
    """
    ahora = timezone.localtime(ahora)
    if enviados is None:
        enviados = {f"T-{pk:02d}" for pk in Checkout.objects.filter(ticket__solicitud__fecha=fecha).values_list("ticket_id", flat=True)}
    bloqueos = bloqueos_por_fecha(fecha, fecha).get(fecha, [])
    bloques = [_armar(t, enviados, ahora) for t in _tickets(solicitud__fecha=fecha)]
    for bloque in bloques:
        bloque["bloqueo"] = next((b for b in bloqueos if b.cubre(fecha, bloque["inicio"], bloque["bloque_id"])), None)
    # AC1: en el orden en que van a llegar.
    return sorted(bloques, key=lambda b: b["inicio"])


def buscar(codigo, enviados=None, ahora=None):
    """Un ticket visible por su código («T-07»), o None."""
    numero = codigo.removeprefix("T-")
    if not numero.isdigit():
        return None
    if enviados is None:
        enviados = [codigo] if Checkout.objects.filter(ticket_id=int(numero)).exists() else []
    # El código se compara entero para que «T-7» no sea otra forma de «T-07».
    t = next((t for t in _tickets(pk=int(numero)) if t["ticket"] == codigo), None)
    return _armar(t, enviados, timezone.localtime(ahora)) if t else None


# --- US-12: historial de sanciones e incidentes, para el administrador ---

# El filtro «Estado de la sanción» del listado: la clave es la que calcula
# historial_personas en `estado_sancion`.
ESTADOS_SANCION = {
    "vigente": "Vigente",
    "levantada": "Levantada",
    "terminada": "Terminada",
    "sin": "Sin sanción",
}


def incidentes():
    """US-12 T2: qué es un incidente, en un solo lugar.

    Hoy, cada pregunta del check-out respondida «No». No hay tabla propia: US-20
    guarda una FotoIntegridad por cada «No», en la misma transacción que el
    check-out, así que contar esas filas es contar las respuestas «No» sin leer
    el JSON. La pregunta y la observación se leen de la copia del listado que
    guarda el check-out (ver detalle_de). Si el equipo decide otra cosa (solo
    algunas secciones, o un check-out con algún «No» como un solo incidente),
    cambia esta función y nada más.
    """
    return FotoIntegridad.objects.all()


def _contar(filas, persona):
    """Cuántas de `filas` son de la persona de la consulta de afuera, como
    subconsulta: así un JOIN del listado (el de las áreas) no multiplica nada."""
    cuantas = filas.filter(**{persona: OuterRef("pk")}).order_by().values(persona).annotate(n=Count("pk")).values("n")
    return Coalesce(Subquery(cuantas, output_field=IntegerField()), 0)


def historial_personas(hoy=None):
    """US-12 T3: una fila por persona, con todo lo que muestra el listado, en
    una sola consulta.

    Entran quienes pueden pedir la sala y quienes alguna vez pidieron o fueron
    sancionados, aunque ya no tengan el rol. Los conteos, la sanción vigente y
    las áreas son subconsultas correlacionadas, no JOIN: filtrar por área no
    duplica filas ni infla los conteos. `estado_sancion` es una de las claves de
    ESTADOS_SANCION: la vigente manda; si no hay, cuenta la última que empezó.
    Las con más incidentes primero; el id desempata para que la paginación no
    repita ni salte filas.
    """
    hoy = hoy or timezone.localdate()
    sanciones = Sancion.objects.filter(usuario=OuterRef("pk"))
    vigente = sanciones.vigentes(hoy).order_by("-termino", "-id")
    ultima = sanciones.order_by("-inicio", "-id")
    # Lo que llega al umbral de inasistencias_para_sancion (T9): las posteriores
    # al inicio de su última sanción, porque las de antes ya se sancionaron.
    desde_ultima = Solicitud.objects.inasistencias(hoy).filter(fecha__gt=Coalesce(
        Subquery(Sancion.objects.filter(usuario=OuterRef("solicitante")).order_by("-inicio", "-id").values("inicio")[:1]),
        Value(date.min),
    ))
    return (
        Usuario.objects.filter(
            Exists(Group.objects.filter(name=Rol.SOLICITANTE, user=OuterRef("pk")))
            | Exists(Solicitud.objects.filter(solicitante=OuterRef("pk")))
            | Exists(sanciones)
        )
        .annotate(
            incidentes=_contar(incidentes(), "checkout__ticket__solicitud__solicitante"),
            inasistencias=_contar(Solicitud.objects.inasistencias(hoy), "solicitante"),
            inasistencias_sin_sancion=_contar(desde_ultima, "solicitante"),
            vigente_id=Subquery(vigente.values("pk")[:1]),
            vigente_motivo=Subquery(vigente.values("motivo")[:1]),
            vigente_termino=Subquery(vigente.values("termino")[:1]),
            ultima_levantada_en=Subquery(ultima.values("levantada_en")[:1]),
            nombres_areas=ArraySubquery(Area.objects.filter(usuarios=OuterRef("pk")).order_by("nombre").values("nombre")),
        )
        .annotate(estado_sancion=Case(
            When(vigente_id__isnull=False, then=Value("vigente")),
            When(~Exists(sanciones), then=Value("sin")),
            When(ultima_levantada_en__isnull=False, then=Value("levantada")),
            default=Value("terminada"),
        ))
        .order_by("-incidentes", "id")
    )


def filtrar_personas(personas, area=None, estado=None, texto=""):
    """Los filtros del listado (T4). El área es un JOIN con
    personas_usuario_areas: una persona está a lo más una vez en cada área, y
    los conteos son subconsultas, así que no se repite nadie."""
    if area:
        personas = personas.filter(areas=area)
    if estado:
        personas = personas.filter(estado_sancion=estado)
    if texto:
        personas = personas.filter(
            Q(email__icontains=texto) | Q(first_name__icontains=texto) | Q(last_name__icontains=texto)
        )
    return personas


def _pregunta(checkout, clave):
    """La sección y el texto de la pregunta, de la copia del listado que guardó
    ese check-out: si el administrador cambió el listado después, se ve lo que
    se preguntó entonces."""
    for seccion in checkout.formulario:
        for pregunta in seccion["preguntas"]:
            if pregunta["id"] == clave:
                return seccion["titulo"], pregunta["texto"]
    return "", clave


def detalle_de(usuario, hoy=None):
    """US-12 T5: los incidentes, las inasistencias y las sanciones de una
    persona, en una sola línea de tiempo, del más antiguo al más reciente.
    Tres consultas, tenga lo que tenga."""
    hoy = hoy or timezone.localdate()
    eventos = []
    fotos = incidentes().filter(checkout__ticket__solicitud__solicitante=usuario).select_related(
        "checkout__ticket__solicitud", "checkout__ticket__bloque", "checkout__registrado_por",
    )
    for foto in fotos:
        checkout = foto.checkout
        seccion, texto = _pregunta(checkout, foto.pregunta)
        eventos.append({
            "tipo": "incidente", "fecha": checkout.ticket.solicitud.fecha, "hora": checkout.ticket.bloque.inicio,
            "bloque": checkout.ticket.bloque, "seccion": seccion, "pregunta": texto,
            "observacion": checkout.respuestas.get(foto.pregunta, {}).get("observacion", ""),
            "registrado_por": checkout.registrado_por, "foto": foto,
        })
    for solicitud in Solicitud.objects.inasistencias(hoy).filter(solicitante=usuario).con_detalle():
        bloques = [sb.bloque for sb in solicitud.solicitudes_bloques.all()]
        eventos.append({
            "tipo": "inasistencia", "fecha": solicitud.fecha, "hora": bloques[0].inicio if bloques else None,
            "solicitud": solicitud, "bloques": bloques,
            "cancelada": solicitud.estado_confirmacion == Solicitud.EstadoConfirmacion.CANCELADA,
        })
    for sancion in Sancion.objects.filter(usuario=usuario).select_related("creada_por", "levantada_por"):
        if sancion.levantada:
            estado = "levantada"
        elif sancion.inicio <= hoy <= sancion.termino:
            estado = "vigente"
        else:
            estado = "terminada"
        eventos.append({"tipo": "sancion", "fecha": sancion.inicio, "hora": None, "sancion": sancion, "estado": estado})
    # El mismo día, lo que pasó en la sala va antes que la sanción que provocó.
    orden = {"inasistencia": 0, "incidente": 1, "sancion": 2}
    return sorted(eventos, key=lambda e: (e["fecha"], orden[e["tipo"]], e["hora"] or datetime.min.time()))
