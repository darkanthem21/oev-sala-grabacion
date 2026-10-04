from django.contrib import admin

from .models import Acompanante, Solicitud, SolicitudBloque


class SolicitudBloqueInline(admin.TabularInline):
    model = SolicitudBloque
    extra = 0


class AcompananteInline(admin.TabularInline):
    model = Acompanante
    extra = 0


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "solicitante",
        "area",
        "estado_validacion",
        "estado_confirmacion",
        "estado_general",
        "sobre_tope_mensual",
        "sobre_bloques_por_solicitud",
        "get_total_personas",
        "creado_en",
    ]
    list_filter = [
        "estado_validacion", "estado_confirmacion", "sobre_tope_mensual",
        "sobre_bloques_por_solicitud", "area", "creado_en",
    ]
    search_fields = ["solicitante__email", "motivo"]
    inlines = [SolicitudBloqueInline, AcompananteInline]

    @admin.display(description="Total personas")
    def get_total_personas(self, obj):
        return obj.total_personas


@admin.register(SolicitudBloque)
class SolicitudBloqueAdmin(admin.ModelAdmin):
    list_display = ["solicitud", "bloque", "fecha"]
    list_filter = ["fecha", "bloque__dia"]


@admin.register(Acompanante)
class AcompananteAdmin(admin.ModelAdmin):
    list_display = ["nombre", "correo", "solicitud"]
    search_fields = ["nombre", "correo", "solicitud__solicitante__email"]
