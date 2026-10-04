import calendar
from datetime import date, datetime, time, timedelta
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings


def obtener_lunes_semana_subsiguiente(fecha_referencia: Optional[date] = None) -> date:
    """
    Retorna la primera fecha pedible (lunes mínimo permitido por desfase).
    """
    from agenda.models import primera_fecha_pedible
    from django.utils import timezone
    if fecha_referencia is not None:
        return primera_fecha_pedible(datetime.combine(fecha_referencia, time(9, 0), tzinfo=timezone.get_current_timezone()))
    return primera_fecha_pedible()


def obtener_limites_reserva(fecha_referencia: Optional[date] = None) -> Tuple[date, date]:
    """
    Calcula los límites inferior y superior de fechas permitidas para reservas.
    - Límite inferior: primera fecha pedible según agenda y parámetros.
    - Límite superior: último día del mes correspondiente a la anticipación máxima permitida.
    """
    from agenda.models import primera_fecha_pedible
    from django.utils import timezone

    if fecha_referencia is not None:
        fecha_minima = primera_fecha_pedible(datetime.combine(fecha_referencia, time(9, 0), tzinfo=timezone.get_current_timezone()))
        base = fecha_referencia
    else:
        fecha_minima = primera_fecha_pedible()
        base = fecha_minima

    meses_anticipacion = getattr(settings, "MESES_ANTICIPACION_MAXIMA", 4)
    try:
        meses_anticipacion = int(meses_anticipacion)
    except (ValueError, TypeError):
        meses_anticipacion = 4

    total_meses = (base.year * 12) + (base.month - 1) + max(meses_anticipacion, 0)
    max_year = total_meses // 12
    max_month = (total_meses % 12) + 1
    _, ultimo_dia = calendar.monthrange(max_year, max_month)
    fecha_maxima = date(max_year, max_month, ultimo_dia)

    return fecha_minima, fecha_maxima


class PasoSolicitud(IntEnum):
    """
    Pasos secuenciales del flujo multipaso (wizard) de solicitud de reserva.
    1: Horario y disponibilidad (Calendario y bloques)
    2: Datos de la actividad (Motivo y acompañantes)
    3: Revisión y confirmación (Términos y condiciones + envío)
    """
    HORARIO = 1
    DATOS = 2
    CONFIRMACION = 3

    @classmethod
    def resolver(cls, valor_raw: Any) -> "PasoSolicitud":
        """
        Resuelve de forma segura el paso actual desde parámetros GET o POST.
        Soporta valores numéricos (1, 2, 3) y nombres de paso ('horario', 'datos', 'confirmacion').
        Si el valor es inválido o no reconocido, retorna HORARIO por defecto.
        """
        try:
            return cls(int(valor_raw))
        except (ValueError, TypeError):
            if isinstance(valor_raw, str):
                nombre_clean = valor_raw.strip().upper()
                if hasattr(cls, nombre_clean):
                    return getattr(cls, nombre_clean)
            return cls.HORARIO

    def validar_acceso(self, sesion_reserva: Dict[str, Any]) -> "PasoSolicitud":
        """
        Verifica si la sesión contiene la información mínima requerida para acceder
        al paso solicitado dentro del asistente de reserva.
        """
        if self >= PasoSolicitud.DATOS:
            if not ("fecha" in sesion_reserva and "bloques_ids" in sesion_reserva):
                return PasoSolicitud.HORARIO

        if self == PasoSolicitud.CONFIRMACION:
            if "motivo" not in sesion_reserva:
                return PasoSolicitud.DATOS

        return self


class SolicitudWizard:
    """
    Encapsula el estado y la persistencia de sesión durante el flujo multipaso de reserva.
    """
    CLAVE_SESION = "solicitud_reserva"

    def __init__(self, session):
        self._session = session

    def _marcar_modificada(self) -> None:
        """Marca la sesión de Django como modificada si el objeto lo soporta."""
        if hasattr(self._session, "modified"):
            self._session.modified = True

    @property
    def datos(self) -> Dict[str, Any]:
        """Retorna los datos almacenados en sesión para la reserva en curso."""
        return self._session.get(self.CLAVE_SESION, {})

    @property
    def tiene_area(self) -> bool:
        """Indica si la sesión ya cuenta con un área académica fijada."""
        datos = self.datos
        return bool(datos.get("area_id") and datos.get("area_nombre"))

    def guardar_area(self, area_id: int, area_nombre: str, reset_horario: bool = False) -> None:
        """Almacena el área académica seleccionada."""
        reserva = self.datos
        if reset_horario or reserva.get("area_id") != area_id:
            reserva.pop("fecha", None)
            reserva.pop("bloques_ids", None)
            reserva.pop("bloques_texto", None)
        reserva["area_id"] = area_id
        reserva["area_nombre"] = area_nombre
        self._session[self.CLAVE_SESION] = reserva
        self._marcar_modificada()

    def limpiar_horario(self) -> None:
        """Reinicia la selección de fecha y bloques en la sesión."""
        reserva = self.datos
        reserva.pop("fecha", None)
        reserva.pop("bloques_ids", None)
        reserva.pop("bloques_texto", None)
        self._session[self.CLAVE_SESION] = reserva
        self._marcar_modificada()

    def guardar_horario(self, fecha_str: str, bloques_ids: List[int], bloques_texto: str) -> None:
        """Almacena la fecha y bloques seleccionados en el Paso 1."""
        reserva = self.datos
        reserva["fecha"] = fecha_str
        reserva["bloques_ids"] = bloques_ids
        reserva["bloques_texto"] = bloques_texto
        self._session[self.CLAVE_SESION] = reserva
        self._marcar_modificada()

    def guardar_datos_actividad(
        self,
        motivo: str,
        observaciones: str,
        personas: int,
        acompanantes: List[Dict[str, str]],
        area_id: Optional[int] = None,
        area_nombre: Optional[str] = None,
    ) -> None:
        """Almacena los datos de la actividad y acompañantes en el Paso 2."""
        reserva = self.datos
        if area_id is not None:
            reserva["area_id"] = area_id
        if area_nombre is not None:
            reserva["area_nombre"] = area_nombre
        reserva["motivo"] = motivo
        reserva["observaciones"] = observaciones
        reserva["personas"] = personas
        reserva["acompanantes"] = acompanantes
        self._session[self.CLAVE_SESION] = reserva
        self._marcar_modificada()

    def obtener_resumen(self) -> Dict[str, Any]:
        """
        Construye una estructura de datos lista para renderizar el resumen
        tanto en el Paso 3 como en la pantalla de éxito final.
        """
        datos = self.datos
        fecha_obj = None
        if "fecha" in datos:
            try:
                fecha_obj = datetime.strptime(datos["fecha"], "%Y-%m-%d").date()
            except ValueError:
                fecha_obj = None

        return {
            "fecha": fecha_obj,
            "fecha_str": datos.get("fecha", ""),
            "bloques_ids": datos.get("bloques_ids", []),
            "bloques_texto": datos.get("bloques_texto", ""),
            "area_id": datos.get("area_id"),
            "area_nombre": datos.get("area_nombre", ""),
            "motivo": datos.get("motivo", ""),
            "observaciones": datos.get("observaciones", ""),
            "personas": datos.get("personas", 1),
            "acompanantes": datos.get("acompanantes", []),
        }

    def limpiar(self) -> None:
        """Elimina el estado temporal del wizard de la sesión al completar la solicitud."""
        self._session.pop(self.CLAVE_SESION, None)
        self._marcar_modificada()
