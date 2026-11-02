"""Registro de modelos de uso y compatibilidad con las migraciones existentes.

La implementación del check-out se encuentra en uso.checkout.models.
"""

from .checkout.models import Checkout, EdicionCheckout, FotoIntegridad, FormularioCheckout, RespuestaCheckout, listado_inicial

__all__ = ["Checkout", "EdicionCheckout", "FotoIntegridad", "FormularioCheckout", "RespuestaCheckout", "listado_inicial"]
