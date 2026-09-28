import calendar
from datetime import date, datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings


def obtener_limites_reserva(fecha_referencia: Optional[date] = None) -> Tuple[date, date]:
    """
    Calcula los límites inferior y superior de fechas permitidas para reservas.
    - Límite inferior: primer día del mes actual (no se permite reservar en meses pasados).
    - Límite superior: último día del mes correspondiente a la anticipación máxima permitida
      (configurable desde el panel administrador o settings.MESES_ANTICIPACION_MAXIMA,
      por defecto 4 meses de distancia hacia el futuro a partir del mes en curso).
    """
    if fecha_referencia is None:
        fecha_referencia = date.today()

    fecha_minima = date(fecha_referencia.year, fecha_referencia.month, 1)

    meses_anticipacion = getattr(settings, "MESES_ANTICIPACION_MAXIMA", 4)
    try:
        meses_anticipacion = int(meses_anticipacion)
    except (ValueError, TypeError):
        meses_anticipacion = 4

    total_meses = (fecha_referencia.year * 12) + (fecha_referencia.month - 1) + max(meses_anticipacion, 0)
    max_year = total_meses // 12
    max_month = (total_meses % 12) + 1
    _, ultimo_dia = calendar.monthrange(max_year, max_month)
    fecha_maxima = date(max_year, max_month, ultimo_dia)

    return fecha_minima, fecha_maxima


class PasoSolicitud(IntEnum):
    """
    Pasos secuenciales del flujo multipaso (wizard) de solicitud de reserva.
    Hereda de IntEnum para mantener compatibilidad natural con enteros en URLs (?paso=1) y plantillas.
    """
    HORARIO = 1
    DATOS = 2
    CONFIRMACION = 3

    @classmethod
    def resolver(cls, valor_raw: Any) -> "PasoSolicitud":
        """
        Resuelve de forma segura el paso actual desde parámetros GET o POST.
        Si el valor es inválido, no numérico o fuera de rango, retorna HORARIO por defecto.
        """
        try:
            return cls(int(valor_raw))
        except (ValueError, TypeError):
            return cls.HORARIO

    def validar_acceso(self, sesion_reserva: Dict[str, Any]) -> "PasoSolicitud":
        """
        Verifica si la sesión contiene la información mínima requerida para acceder
        al paso solicitado. Si falta información previa, redirige al paso correspondiente.
        """
        if self >= PasoSolicitud.DATOS:
            if not ("fecha" in sesion_reserva and "bloques_ids" in sesion_reserva):
                return PasoSolicitud.HORARIO

        if self == PasoSolicitud.CONFIRMACION:
            if not ("area_id" in sesion_reserva and "motivo" in sesion_reserva):
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
        area_id: int,
        area_nombre: str,
        motivo: str,
        observaciones: str,
        personas: int,
        acompanantes: List[Dict[str, str]],
    ) -> None:
        """Almacena los datos de la actividad y acompañantes en el Paso 2."""
        reserva = self.datos
        reserva["area_id"] = area_id
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
