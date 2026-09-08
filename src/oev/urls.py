from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from django.views.generic import RedirectView

from agenda import views as agenda
from configuracion import views as configuracion
from personas import views

urlpatterns = [
    path("", views.panel, name="panel"),
    path("login/", views.entrar, name="login"),
    path("logout/", auth.LogoutView.as_view(next_page="login"), name="logout"),
    # US-01 AC6: las cuatro vistas de recuperacion las trae Django, con enlace
    # firmado y sin tabla propia. Solo ponemos las plantillas.
    path("clave/", auth.PasswordResetView.as_view(
        template_name="personas/clave_pedir.html",
        email_template_name="personas/clave_correo.txt",
        success_url="/clave/enviada/"), name="password_reset"),
    path("clave/enviada/", auth.PasswordResetDoneView.as_view(
        template_name="personas/clave_enviada.html"), name="password_reset_done"),
    path("clave/<uidb64>/<token>/", auth.PasswordResetConfirmView.as_view(
        template_name="personas/clave_nueva.html",
        success_url="/clave/lista/"), name="password_reset_confirm"),
    path("clave/lista/", auth.PasswordResetCompleteView.as_view(
        template_name="personas/clave_lista.html"), name="password_reset_complete"),
    # US-04. Cada pestaña del panel la sirve su propio modulo: los bloques son de
    # agenda, no de configuracion, y asi `configuracion` sigue sin depender de
    # nadie (README.md). El cascaron con las pestañas es una plantilla compartida.
    # US-01 + US-04: la administracion entra por su propia puerta. Reusa `entrar`,
    # asi que comparte autenticacion, bloqueo por intentos y recuperacion de clave.
    path(
        "configuracion/entrar/",
        views.entrar,
        {"plantilla": "personas/gestion.html", "ruta": "login_gestion", "solo_staff": True},
        name="login_gestion",
    ),
    path("configuracion/", RedirectView.as_view(pattern_name="panel_bloques")),
    path("configuracion/bloques/", agenda.bloques, name="panel_bloques"),
    path("configuracion/bloques/editar/", agenda.editar_bloque, name="editar_bloque"),
    path("configuracion/areas/", configuracion.seccion, {"pestana": "areas"}, name="panel_areas"),
    path("configuracion/reglas/", configuracion.seccion, {"pestana": "reglas"}, name="panel_reglas"),
    path("admin/", admin.site.urls),
]
