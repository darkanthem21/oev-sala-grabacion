from django.urls import path

from . import views

urlpatterns = [
    path("", views.solicitar, name="solicitar"),
    path("area/", views.solicitar_area, name="solicitar_area"),
    path("calendario/", views.calendario, name="calendario"),
    path("bloques/", views.bloques_dia, name="bloques_dia"),
]
