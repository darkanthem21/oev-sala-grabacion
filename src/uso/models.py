"""Registro de modelos de uso y compatibilidad con las migraciones existentes.

La implementación del check-out se encuentra en uso.checkout.models.
"""

from .checkout.models import Checkout, FotoIntegridad, FormularioCheckout, listado_inicial

__all__ = ["Checkout", "FotoIntegridad", "FormularioCheckout", "listado_inicial"]
