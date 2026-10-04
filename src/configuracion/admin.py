from django.contrib import admin

from .models import CambioParametro, Parametros


# RNF 2, igual que en `agenda`: quien herede el sistema tiene que poder arreglar
# una fila mala sin llamar a nadie. La operación diaria va por el panel.
@admin.register(Parametros)
class ParametrosAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not Parametros.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CambioParametro)
class CambioParametroAdmin(admin.ModelAdmin):
    """Solo lectura, porque una bitácora que se puede editar no registra nada."""

    list_display = ["cuando", "etiqueta", "antes", "despues", "quien"]
    list_filter = ["campo", "quien"]
    date_hierarchy = "cuando"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
