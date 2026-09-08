from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Area, Usuario


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "prioridad", "activa"]
    list_filter = ["activa"]


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
