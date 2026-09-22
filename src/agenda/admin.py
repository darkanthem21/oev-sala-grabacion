from django.contrib import admin

from .models import Bloque


# RNF 2: quien herede el sistema tiene que poder arreglar una fila mala sin
# llamar a nadie. La operación diaria va por el panel.
@admin.register(Bloque)
class BloqueAdmin(admin.ModelAdmin):
    list_display = ["dia", "inicio", "termino", "activo"]
    list_filter = ["dia", "activo"]
    ordering = ["dia", "inicio"]
