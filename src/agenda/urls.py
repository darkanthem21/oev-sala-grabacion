from django.urls import path
from . import views

urlpatterns = [
    path("calendario/", views.calendario, name="calendario"),
    path("bloques/", views.bloques_dia, name="bloques_dia"),
]
