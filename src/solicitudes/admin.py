from django.contrib import admin

from .models import Acompanante, Solicitud, SolicitudBloque


def _resuelta(solicitud):
    """US-11 T5: lo resuelto es historial. Ni se borra ni se edita, ni la
    solicitud ni sus bloques ni sus acompañantes, para que el historial muestre
    lo que se envió y lo que se decidió."""
    return solicitud is not None and solicitud.resuelta_en is not None


class DeSolicitudResueltaInline(admin.TabularInline):
    """En línea, `obj` es la solicitud que los contiene."""

    extra = 0

    def has_add_permission(self, request, obj=None):
        return not _resuelta(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not _resuelta(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not _resuelta(obj) and super().has_delete_permission(request, obj)


class SolicitudBloqueInline(DeSolicitudResueltaInline):
    model = SolicitudBloque


class AcompananteInline(DeSolicitudResueltaInline):
    model = Acompanante


class DeSolicitudResueltaAdmin(admin.ModelAdmin):
    """Bloques y acompañantes también tienen su propia página en /admin/: ahí
    `obj` es la fila, y la solicitud es la suya."""

    def has_change_permission(self, request, obj=None):
        return not (obj and _resuelta(obj.solicitud)) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not (obj and _resuelta(obj.solicitud)) and super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Ni agregar uno nuevo a una resuelta ni mover uno a ella.
        if db_field.name == "solicitud":
            kwargs["queryset"] = Solicitud.objects.filter(resuelta_en__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "solicitante",
        "area",
        "fecha",
        "estado_validacion",
        "estado_confirmacion",
        "estado_general",
        "get_total_personas",
        "creado_en",
    ]
    list_filter = ["fecha", "estado_validacion", "estado_confirmacion", "area", "creado_en"]
    search_fields = ["solicitante__email", "motivo"]
    inlines = [SolicitudBloqueInline, AcompananteInline]
    # US-07: aprobar desde acá saltaría la regla de un aprobado por bloque y
    # fecha (AC3). Se resuelve en el panel del validador.
    readonly_fields = [
        "estado_validacion", "motivo_resolucion", "resuelta_por", "resuelta_en", "asignada_a",
        "recordatorio_enviado_en", "cancelada_en",
    ]

    @admin.display(description="Total personas")
    def get_total_personas(self, obj):
        return obj.total_personas

    # Sin permiso de cambio, Django muestra la ficha entera de solo lectura y
    # rechaza el POST. El borrado en lote pregunta fila por fila
    # (get_deleted_objects), así que una resuelta tampoco cae entre otras.
    def has_change_permission(self, request, obj=None):
        return not _resuelta(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not _resuelta(obj) and super().has_delete_permission(request, obj)


@admin.register(SolicitudBloque)
class SolicitudBloqueAdmin(DeSolicitudResueltaAdmin):
    list_display = ["solicitud", "bloque", "fecha"]
    # La fecha es la de la solicitud (propiedad): se trae junto para no
    # consultar una vez por fila.
    list_select_related = ["solicitud", "bloque"]
    list_filter = ["solicitud__fecha", "bloque__dia"]


@admin.register(Acompanante)
class AcompananteAdmin(DeSolicitudResueltaAdmin):
    list_display = ["nombre", "correo", "solicitud"]
    search_fields = ["nombre", "correo", "solicitud__solicitante__email"]
