import calendar
from collections import defaultdict
from dataclasses import dataclass
from functools import partial
from datetime import date, datetime, time
from typing import Any, Dict, List, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from agenda.models import Bloque, disponibilidad, impedimento
from agenda.signals import Pedido
from notificaciones.services import avisar
from personas.models import Area
from django.urls import reverse

from .models import Acompanante, Solicitud, SolicitudBloque


def revisar_acompanantes(formset, esperados: int, correo_solicitante: str) -> Tuple[List[Any], List[str]]:
    """Cruza las filas llenas con la cantidad de personas declarada.

    Valida que los acompañantes requeridos estén completos, sin correos repetidos
    y sin duplicar la cuenta del propio solicitante (US-02 AC6).
    Devuelve (filas_llenas, lista_de_errores).
    """
    llenos = [f for f in formset.forms if f.esta_lleno]
    errores = []

    if len(llenos) != esperados:
        errores.append(
            f"Declaraste {esperados + 1} personas en sala, así que faltan los datos "
            f"de {esperados} acompañante(s); tienes {len(llenos)} completo(s)."
        )

    # US-02 AC6: si dos filas traen el mismo correo no hay identificación que
    # valga, y el correo es lo único que distingue a una persona de otra.
    correos = [f.cleaned_data["correo"].lower() for f in llenos if f.cleaned_data.get("correo")]
    if len(correos) != len(set(correos)):
        errores.append("Hay un correo repetido entre los acompañantes.")
    if correo_solicitante and correo_solicitante.lower() in correos:
        errores.append("Tu propio correo ya está incluido: eres parte de la cuenta de personas.")

    return llenos, errores


@dataclass
class BloqueVista:
    """Un bloque de la jornada de un día, como lo ve un usuario al elegir horario.

    Los aceptados no llegan hasta acá: obtener_bloques_dia_para_usuario los
    deja fuera. Los que el usuario ya tiene pendientes se muestran, marcados y
    sin poder elegirse otra vez.
    """

    id: int
    inicio: time
    termino: time
    es_propio: bool = False

    @property
    def disponible_para_reserva(self) -> bool:
        return not self.es_propio

    @property
    def texto(self) -> str:
        return f"{self.inicio:%H:%M} – {self.termino:%H:%M}"


def obtener_dias_con_disponibilidad(year: int, month: int) -> set:
    """Retorna un conjunto de números de día del mes que tienen al menos un bloque disponible."""
    _, ultimo_dia = calendar.monthrange(year, month)
    desde = date(year, month, 1)
    hasta = date(year, month, ultimo_dia)

    jornada_mes = disponibilidad(desde, hasta)
    if not jornada_mes:
        return set()

    # Obtener todas las reservas aceptadas en el rango de fechas
    bloques_ocupados = set(
        SolicitudBloque.objects.filter(
            solicitud__fecha__gte=desde,
            solicitud__fecha__lte=hasta,
            solicitud__estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
            solicitud__estado_confirmacion__in=[
                Solicitud.EstadoConfirmacion.NO_HABILITADA,
                Solicitud.EstadoConfirmacion.PENDIENTE,
                Solicitud.EstadoConfirmacion.CONFIRMADA,
            ],
        ).values_list("solicitud__fecha", "bloque_id")
    )

    dias_disponibles = set()
    for fecha, bloques in jornada_mes.items():
        for b in bloques:
            if (fecha, b.id) not in bloques_ocupados:
                dias_disponibles.add(fecha.day)
                break

    return dias_disponibles


def obtener_bloques_dia_para_usuario(fecha: date, usuario=None) -> List["BloqueVista"]:
    """Retorna los bloques de la jornada configurada para una fecha visibles para el usuario:
    - Bloques disponibles (sin reservas aceptadas).
    - Bloques con solicitud activa propia del usuario (marcado con es_propio=True).
    Excluye:
    - Bloques con reserva aceptada.
    """
    bloques_plantilla = disponibilidad(fecha, fecha).get(fecha, [])
    if not bloques_plantilla:
        return []

    bloques_ids = [b.id for b in bloques_plantilla]

    # Obtener relaciones para esa fecha
    relaciones = (
        SolicitudBloque.objects.filter(
            solicitud__fecha=fecha,
            bloque_id__in=bloques_ids,
            solicitud__estado_validacion__in=[
                Solicitud.EstadoValidacion.PENDIENTE,
                Solicitud.EstadoValidacion.ACEPTADA,
            ],
        )
        .exclude(solicitud__estado_confirmacion=Solicitud.EstadoConfirmacion.CANCELADA)
        .select_related("solicitud", "solicitud__solicitante")
    )

    solicitudes_por_bloque = {}
    for rel in relaciones:
        solicitudes_por_bloque.setdefault(rel.bloque_id, []).append(rel.solicitud)

    usuario_id = usuario.id if (usuario and getattr(usuario, "is_authenticated", False)) else None

    resultado = []
    for b in sorted(bloques_plantilla, key=lambda x: x.inicio):
        sols = solicitudes_por_bloque.get(b.id, [])

        # Si el bloque tiene una solicitud ACEPTADA, no se muestra
        if any(s.estado_validacion == Solicitud.EstadoValidacion.ACEPTADA for s in sols):
            continue

        # Si el usuario actual tiene una solicitud PENDIENTE para este bloque:
        es_propio = bool(usuario_id) and any(
            s.solicitante_id == usuario_id and s.estado_validacion == Solicitud.EstadoValidacion.PENDIENTE
            for s in sols
        )
        resultado.append(BloqueVista(id=b.id, inicio=b.inicio, termino=b.termino, es_propio=es_propio))

    return resultado


def guardar_solicitud_completa(
    usuario,
    datos_reserva: Dict[str, Any],
) -> Solicitud:
    """Crea y persiste una nueva Solicitud, sus SolicitudBloque y Acompanantes de forma atómica."""
    # US-10 T2: la vista ya no muestra el formulario a quien está sancionado.
    # Esto es para el POST que llega igual, armado a mano o desde una pestaña
    # que quedó abierta antes de la sanción.
    sancion = usuario.sancion_vigente
    if sancion is not None:
        raise ValidationError(
            f"Tienes una sanción vigente hasta el {sancion.hasta}: no puedes enviar solicitudes."
        )
    with transaction.atomic():
        area = Area.objects.get(id=datos_reserva["area_id"])
        fecha_obj = datos_reserva.get("fecha")
        if isinstance(fecha_obj, str):
            fecha_obj = datetime.strptime(fecha_obj, "%Y-%m-%d").date()

        solicitud = Solicitud(
            solicitante=usuario,
            area=area,
            fecha=fecha_obj,
            motivo=datos_reserva.get("motivo", "").strip(),
            observaciones=datos_reserva.get("observaciones", "").strip(),
            personas=datos_reserva.get("personas", 1),
            estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
            estado_confirmacion=Solicitud.EstadoConfirmacion.NO_HABILITADA,
        )
        solicitud.full_clean()
        solicitud.save()

        bloques_ids = datos_reserva.get("bloques_ids", [])
        # Si un bloque ya no se puede pedir esa fecha, lo dice el full_clean de
        # cada SolicitudBloque (`impedimento`).
        bloques_db = Bloque.objects.filter(id__in=bloques_ids)
        if len(bloques_db) != len(bloques_ids):
            raise ValidationError("Uno o más bloques seleccionados no son válidos o ya no están activos.")

        for b in bloques_db:
            sol_bloque = SolicitudBloque(solicitud=solicitud, bloque=b)
            sol_bloque.full_clean()
            sol_bloque.save()

        for acomp in datos_reserva.get("acompanantes", []):
            if acomp.get("nombre") and acomp.get("correo"):
                Acompanante.objects.create(
                    solicitud=solicitud,
                    nombre=acomp["nombre"].strip(),
                    correo=acomp["correo"].strip().lower(),
                )

        return solicitud


def retirar_solicitud(usuario, solicitud_id: int) -> bool:
    """Retira una solicitud propia que el validador todavía no revisa.

    Pasa a RETIRADA y no se borra: sigue en el historial. La disponibilidad y
    la regla de bloque ya pedido solo cuentan las pendientes y aceptadas, así
    que el bloque queda libre para pedirlo de nuevo.

    Es un solo UPDATE condicionado al estado: si el validador la acepta o
    rechaza en el mismo instante, no se pisa su decisión. Devuelve si se retiró.
    """
    return Solicitud.objects.filter(
        pk=solicitud_id,
        solicitante=usuario,
        estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
    ).update(
        estado_validacion=Solicitud.EstadoValidacion.RETIRADA,
        # update() se salta auto_now.
        actualizado_en=timezone.now(),
    ) == 1


def pedidos_vivos(sender, desde, hasta=None, bloque=None, **kwargs):
    """Los bloques que piden las solicitudes pendientes y las aprobadas sin
    cancelar desde `desde`, para que agenda sepa a quién le quita la sala cuando
    saca horario. Se conecta en `apps.py`."""
    filas = SolicitudBloque.objects.filter(
        solicitud__fecha__gte=desde,
        solicitud__estado_validacion__in=[
            Solicitud.EstadoValidacion.PENDIENTE, Solicitud.EstadoValidacion.ACEPTADA,
        ],
    ).exclude(
        solicitud__estado_confirmacion=Solicitud.EstadoConfirmacion.CANCELADA,
    ).select_related("bloque", "solicitud__solicitante")
    if hasta is not None:
        filas = filas.filter(solicitud__fecha__lte=hasta)
    if bloque is not None:
        filas = filas.filter(bloque_id=bloque)
    return [
        Pedido(
            solicitud=f.solicitud_id,
            codigo=f.ticket,
            fecha=f.fecha,
            bloque=f.bloque_id,
            inicio=f.inicio,
            termino=f.termino,
            pendiente=f.solicitud.estado_validacion == Solicitud.EstadoValidacion.PENDIENTE,
            solicitante=f.solicitud.solicitante.get_full_name() or f.solicitud.solicitante.email,
            correo=f.solicitud.solicitante.email,
        )
        for f in filas
    ]


def liberar(sender, afectadas, razon, quien, **kwargs):
    """Lo que les pasa a las solicitudes que pierden su horario: la pendiente
    se rechaza con la razón y la aprobada se cancela, cada una con su correo.
    Se afecta la solicitud entera, como al validar.

    Corre dentro de la transacción que guarda el corte. Las filas se bloquean en
    orden de id, igual que en `resolver`, y lo que alguien resolvió entremedio
    se salta.
    """
    ids = sorted({p.solicitud for p in afectadas})
    filas = Solicitud.objects.select_for_update(of=("self",)).filter(pk__in=ids).order_by("pk")
    ahora = timezone.now()
    canceladas = defaultdict(list)
    for s in filas.select_related("solicitante"):
        if s.estado_validacion == Solicitud.EstadoValidacion.PENDIENTE:
            s.estado_validacion = Solicitud.EstadoValidacion.RECHAZADA
            s.motivo_resolucion = razon
            s.resuelta_por, s.resuelta_en = quien, ahora
            s.save(update_fields=[
                "estado_validacion", "motivo_resolucion", "resuelta_por", "resuelta_en", "actualizado_en",
            ])
            _avisar_resolucion(s)
        elif (s.estado_validacion == Solicitud.EstadoValidacion.ACEPTADA
              and s.estado_confirmacion != Solicitud.EstadoConfirmacion.CANCELADA):
            s.estado_confirmacion = Solicitud.EstadoConfirmacion.CANCELADA
            s.save(update_fields=["estado_confirmacion", "actualizado_en"])
            canceladas[s.solicitante].append(s)
    # Uno por persona, con todas sus reservas; si uno falla, los demás igual salen.
    for persona, solicitudes in canceladas.items():
        transaction.on_commit(
            partial(
                avisar,
                persona.email,
                "Tu reserva de la sala de grabación se canceló",
                "notificaciones/bloqueo.txt",
                {"nombre": persona.get_full_name() or persona.email, "razon": razon, "solicitudes": solicitudes},
            ),
            robust=True,
        )


# US-07 AC4: el motivo le llega al solicitante, así que tiene que decir algo.
# El panel exige lo mismo antes de enviar.
MINIMO_MOTIVO = 10


def _rivales(solicitud):
    """US-07 AC2: las otras pendientes que piden alguno de sus bloques el mismo día."""
    return Solicitud.objects.filter(
        fecha=solicitud.fecha,
        estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
        solicitudes_bloques__bloque__in=solicitud.solicitudes_bloques.values("bloque"),
    ).exclude(pk=solicitud.pk)


def _avisar_resolucion(solicitud, asignada=None, url_base=""):
    """AC4: un correo por solicitud, cuando la resolución se confirma. El de una
    aceptada trae el enlace para confirmar la asistencia (US-03)."""
    persona = solicitud.solicitante
    url_confirmar = ""
    if url_base and solicitud.estado_validacion == Solicitud.EstadoValidacion.ACEPTADA:
        url_confirmar = url_base + reverse("confirmar_solicitud", args=[solicitud.pk])
    transaction.on_commit(
        partial(
            avisar,
            persona.email,
            f"Tu solicitud de la sala de grabación fue {solicitud.get_estado_validacion_display().lower()}",
            "notificaciones/resolucion.txt",
            {
                "nombre": persona.get_full_name() or persona.email,
                "solicitud": solicitud,
                "bloques": [
                    sb.bloque for sb in
                    solicitud.solicitudes_bloques.select_related("bloque").order_by("bloque__inicio")
                ],
                "asignada": asignada,
                "url_confirmar": url_confirmar,
            },
        ),
        robust=True,
    )


@transaction.atomic
def resolver(solicitud_id, aprobar, motivo, quien, url_base=""):
    """US-07: aprueba o rechaza una solicitud entera; devuelve las que cambiaron.

    Aprobar rechaza enteras a sus rivales con el mismo motivo (AC2 y AC4). AC3
    se sostiene con bloqueos de fila: la solicitud y sus rivales se bloquean en
    orden de id, así dos validadores que resuelven el mismo bloque a la vez
    quedan en fila y el segundo ve lo que decidió el primero.

    `url_base` (esquema y dominio) arma el enlace absoluto de confirmación del
    correo; sin él, el correo sale sin enlace.
    """
    solicitud = Solicitud.objects.filter(pk=solicitud_id).first()
    if solicitud is None:
        raise ValidationError("Esta solicitud ya no existe.")
    # FOR UPDATE no admite DISTINCT, así que primero los ids y después el bloqueo.
    ids = {solicitud.pk, *_rivales(solicitud).values_list("pk", flat=True)}
    filas = {s.pk: s for s in Solicitud.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    solicitud = filas.pop(solicitud.pk)
    if solicitud.estado_validacion != Solicitud.EstadoValidacion.PENDIENTE:
        raise ValidationError("Esta solicitud ya fue resuelta o retirada. Recarga la página para ver lo último.")
    rivales = [s for s in filas.values() if s.estado_validacion == Solicitud.EstadoValidacion.PENDIENTE]
    motivo = (motivo or "").strip()

    if aprobar:
        pedidos = list(solicitud.solicitudes_bloques.select_related("bloque"))
        for pedido in pedidos:
            # Quitado, bloqueado (US-17 AC3) o ajeno a la fecha: no se aprueba.
            razon = impedimento(pedido.bloque, solicitud.fecha)
            if razon is not None:
                raise ValidationError(f"{razon} No se puede aprobar: recházala.")
        ocupada = Solicitud.objects.filter(
            fecha=solicitud.fecha,
            estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
            solicitudes_bloques__bloque__in=[p.bloque_id for p in pedidos],
        ).exclude(estado_confirmacion=Solicitud.EstadoConfirmacion.CANCELADA)
        if ocupada.exists():
            raise ValidationError("Uno de sus bloques ya está aprobado para otra solicitud ese día.")
        if rivales and len(motivo) < MINIMO_MOTIVO:
            raise ValidationError(
                f"Escribe el motivo del rechazo de las otras solicitudes (mínimo {MINIMO_MOTIVO} caracteres). "
                "Si no las ves, recarga la página."
            )
    elif len(motivo) < MINIMO_MOTIVO:
        raise ValidationError(f"Escribe el motivo del rechazo (mínimo {MINIMO_MOTIVO} caracteres).")

    estado = Solicitud.EstadoValidacion.ACEPTADA if aprobar else Solicitud.EstadoValidacion.RECHAZADA
    cambios = [(solicitud, estado)]
    if aprobar:
        cambios += [(r, Solicitud.EstadoValidacion.RECHAZADA) for r in rivales]
    ahora = timezone.now()
    for s, e in cambios:
        # El motivo es de quien queda rechazado: la aprobada no lo lleva, ni en
        # la base ni en su correo.
        s.estado_validacion = e
        s.motivo_resolucion = motivo if e == Solicitud.EstadoValidacion.RECHAZADA else ""
        s.resuelta_por, s.resuelta_en = quien, ahora
        s.asignada_a = None if s is solicitud else solicitud
        s.save(update_fields=[
            "estado_validacion", "motivo_resolucion", "resuelta_por", "resuelta_en", "asignada_a",
            "actualizado_en",
        ])
        _avisar_resolucion(s, asignada=s.asignada_a, url_base=url_base)
    return [s for s, _ in cambios]


def confirmar_solicitud(usuario, solicitud_id):
    """US-03: quien pidió confirma que va a usar la sala, a más tardar el día
    anterior. Un solo UPDATE condicionado, como retirar_solicitud: si ya no
    cumple (ajena, sin aceptar, ya confirmada o cancelada, o es hoy), no cambia
    nada. Devuelve si se confirmó."""
    return Solicitud.objects.filter(
        pk=solicitud_id,
        solicitante=usuario,
        estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
        estado_confirmacion__in=[Solicitud.EstadoConfirmacion.NO_HABILITADA, Solicitud.EstadoConfirmacion.PENDIENTE],
        fecha__gt=timezone.localdate(),
    ).update(
        estado_confirmacion=Solicitud.EstadoConfirmacion.CONFIRMADA,
        actualizado_en=timezone.now(),
    ) == 1
