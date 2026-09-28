from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path("bloques/", views.bloques_dia, name="agenda_bloques_dia"),
    path("disponibilidad/", views.disponibilidad_mes, name="agenda_disponibilidad_mes"),
    path("calendario/", RedirectView.as_view(url="/solicitar/calendario/", permanent=False)),
]
