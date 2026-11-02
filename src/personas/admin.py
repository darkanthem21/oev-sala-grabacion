from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import transaction

from . import services
from .models import Area, CambioArea, Sancion, Usuario


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    """US-05: la operación diaria va por la pestaña Áreas. Acá queda para
    arreglar una fila, sin borrar (AC3) y con el mismo registro (AC6)."""

    list_display = ["nombre", "prioridad", "activa"]
    list_filter = ["activa"]

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        cambios = services.cambios_de_area(form)
        super().save_model(request, obj, form, change)
        services.registrar_cambios(obj, cambios, request.user)


@admin.register(CambioArea)
class CambioAreaAdmin(admin.ModelAdmin):
    """Solo lectura, porque un registro que se puede editar no registra nada."""

    list_display = ["cuando", "area", "etiqueta", "antes", "despues", "quien"]
    list_filter = ["area", "campo"]
    date_hierarchy = "cuando"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_active"]
    list_filter = ["is_active", "is_staff", "areas"]
    search_fields = ["email", "first_name", "last_name"]
    filter_horizontal = ["areas", "groups", "user_permissions"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personales", {"fields": ("first_name", "last_name", "areas")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Acceso", {"fields": ("last_login", "intentos_fallidos", "bloqueado_hasta")}),
    )
    add_fieldsets = ((None, {"fields": ("email", "password1", "password2")}),)


@admin.register(Sancion)
class SancionAdmin(admin.ModelAdmin):
    """US-10: acá se crean y se acortan las sanciones, solo el superusuario.

    El rol administrador no entra a esta pantalla: levanta desde la pestaña
    Sanciones del panel, que deja el registro completo. Por eso lo del
    levantamiento es de solo lectura acá, y nada se borra: una sanción borrada
    es una que nunca quedó registrada.
    """

    list_display = ["usuario", "motivo", "inicio", "termino", "creada_por", "levantada_en"]
    list_filter = [("levantada_en", admin.EmptyFieldListFilter), "inicio"]
    search_fields = ["usuario__email", "usuario__first_name", "usuario__last_name", "motivo"]
    date_hierarchy = "inicio"
    autocomplete_fields = ["usuario"]
    readonly_fields = ["creada_por", "creada_en", "levantada_por", "levantada_en", "motivo_levantamiento"]

    def _solo_superusuario(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    has_view_permission = _solo_superusuario
    has_add_permission = _solo_superusuario
    has_change_permission = _solo_superusuario

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creada_por = request.user
        super().save_model(request, obj, form, change)
