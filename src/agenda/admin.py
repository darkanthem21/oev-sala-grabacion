from django.contrib import admin

from .models import Bloque, Bloqueo


# RNF 2: quien herede el sistema tiene que poder arreglar una fila mala sin
# llamar a nadie. La operación diaria va por el panel.
@admin.register(Bloque)
class BloqueAdmin(admin.ModelAdmin):
    list_display = ["dia", "inicio", "termino", "activo"]
    list_filter = ["dia", "activo"]
    ordering = ["dia", "inicio"]


@admin.register(Bloqueo)
class BloqueoAdmin(admin.ModelAdmin):
    """US-17 AC6: el historial completo. El panel muestra solo lo último.

    Se puede corregir una fila, pero no quién ni cuándo, y no se borra: un
    bloqueo borrado es una mantención que nunca quedó registrada. Tampoco se
    crea acá, porque el panel es el que avisa a las reservas afectadas (AC4).
    """

    list_display = ["desde", "hasta", "bloque", "motivo", "detalle", "bloqueado_por",
                    "bloqueado_en", "levantado_por", "levantado_en"]
    list_filter = ["motivo", ("levantado_en", admin.EmptyFieldListFilter)]
    date_hierarchy = "desde"
    readonly_fields = ["bloqueado_por", "bloqueado_en", "levantado_por", "levantado_en"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
