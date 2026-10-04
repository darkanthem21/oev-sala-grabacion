import calendar
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction

from agenda.models import Bloque, disponibilidad, primera_fecha_pedible
from agenda.signals import Reserva
from personas.models import Area
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
            fecha__gte=desde,
            fecha__lte=hasta,
            solicitud__estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
            solicitud__estado_confirmacion__in=[
                Solicitud.EstadoConfirmacion.NO_HABILITADA,
                Solicitud.EstadoConfirmacion.PENDIENTE,
                Solicitud.EstadoConfirmacion.CONFIRMADA,
            ],
        ).values_list("fecha", "bloque_id")
    )

    dias_disponibles = set()
    for fecha, bloques in jornada_mes.items():
        for b in bloques:
            if (fecha, b.id) not in bloques_ocupados:
                dias_disponibles.add(fecha.day)
                break

    return dias_disponibles


def obtener_bloques_dia_para_usuario(fecha: date, usuario=None) -> List[Any]:
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
            fecha=fecha,
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

        item = type("BloqueVista", (), {
            "id": b.id,
            "inicio": b.inicio,
            "termino": b.termino,
            "hora_inicio": b.inicio,
            "hora_final": b.termino,
            "texto": f"{b.inicio.strftime('%H:%M')} – {b.termino.strftime('%H:%M')}",
            "disponible": True,
            "es_propio": False,
            "disponible_para_reserva": True,
        })()

        # Si el usuario actual tiene una solicitud PENDIENTE para este bloque:
        if usuario_id and any(
            s.solicitante_id == usuario_id and s.estado_validacion == Solicitud.EstadoValidacion.PENDIENTE
            for s in sols
        ):
            item.es_propio = True
            item.disponible_para_reserva = False

        resultado.append(item)

    return resultado


def guardar_solicitud_completa(
    usuario,
    datos_reserva: Dict[str, Any],
) -> Solicitud:
    """Crea y persiste una nueva Solicitud, sus SolicitudBloque y Acompanantes de forma atómica."""
    with transaction.atomic():
        area = Area.objects.get(id=datos_reserva["area_id"])
        fecha_obj = datos_reserva.get("fecha")
        if isinstance(fecha_obj, str):
            fecha_obj = datetime.strptime(fecha_obj, "%Y-%m-%d").date()

        solicitud = Solicitud(
            solicitante=usuario,
            area=area,
            motivo=datos_reserva.get("motivo", "").strip(),
            observaciones=datos_reserva.get("observaciones", "").strip(),
            personas=datos_reserva.get("personas", 1),
            estado_validacion=Solicitud.EstadoValidacion.PENDIENTE,
            estado_confirmacion=Solicitud.EstadoConfirmacion.NO_HABILITADA,
        )
        solicitud.full_clean()
        solicitud.save()

        bloques_ids = datos_reserva.get("bloques_ids", [])
        bloques_db = Bloque.objects.filter(id__in=bloques_ids, activo=True)
        if len(bloques_db) != len(bloques_ids):
            raise ValidationError("Uno o más bloques seleccionados no son válidos o ya no están activos.")

        for b in bloques_db:
            sol_bloque = SolicitudBloque(
                solicitud=solicitud,
                bloque=b,
                fecha=fecha_obj,
            )
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


def reservas_aprobadas(sender, desde, hasta, **kwargs):
    """US-17 AC4: las reservas aceptadas y no canceladas de esas fechas, para que
    agenda sepa a quién le quita la sala un bloqueo. Se conecta en `apps.py`."""
    filas = SolicitudBloque.objects.filter(
        fecha__range=(desde, hasta),
        solicitud__estado_validacion=Solicitud.EstadoValidacion.ACEPTADA,
    ).exclude(
        solicitud__estado_confirmacion=Solicitud.EstadoConfirmacion.CANCELADA,
    ).select_related("bloque", "solicitud__solicitante")
    return [
        Reserva(
            codigo=f.ticket,
            fecha=f.fecha,
            inicio=f.inicio,
            termino=f.termino,
            solicitante=f.solicitud.solicitante.get_full_name() or f.solicitud.solicitante.email,
            correo=f.solicitud.solicitante.email,
        )
        for f in filas
    ]
