from django.urls import path

from . import views

urlpatterns = [
    path("", views.solicitar, name="solicitar"),
    path("enviada/<int:solicitud_id>/", views.enviada, name="solicitud_enviada"),
    path("area/", views.solicitar_area, name="solicitar_area"),
    path("calendario/", views.calendario, name="calendario"),
    path("bloques/", views.bloques_dia, name="bloques_dia"),
    path("mis-solicitudes/", views.mis_solicitudes, name="mis_solicitudes"),
    path("mis-solicitudes/<int:solicitud_id>/retirar/", views.retirar, name="retirar_solicitud"),
    path("validacion/", views.panel_validador, name="panel_validador"),
]
