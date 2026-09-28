from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path
from django.views.generic import RedirectView

from agenda import views as agenda
from configuracion import views as configuracion
from personas import views
from personas.models import Rol
from solicitudes import views as solicitudes
from uso import views as uso

urlpatterns = [
    path("", views.panel, name="panel"),
    path("solicitar/", include("solicitudes.urls")),
    path("validador/", solicitudes.panel_validador, name="panel_validador"),
    path("login/", views.entrar, name="login"),
    path("logout/", auth.LogoutView.as_view(next_page="login"), name="logout"),
    # US-01 AC6: las cuatro vistas de recuperación las trae Django, con enlace
    # firmado y sin tabla propia. Nosotros solo ponemos las plantillas.
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
    # US-04. Cada pestaña del panel la sirve su propio módulo: los bloques son de
    # agenda, así `configuracion` sigue sin depender de nadie (README.md). El
    # cascarón con las pestañas es una plantilla compartida.
    # US-08 AC4: una puerta por rol, ninguna enlazada desde el sitio público.
    # Todas reusan `entrar`, así que comparten autenticación, bloqueo por intentos
    # y recuperación de clave. Lo que cambia es el encabezado y el grupo que dejan
    # pasar.
    path(
        "configuracion/entrar/",
        views.entrar,
        {"plantilla": "personas/gestion.html", "ruta": "login_gestion",
         "rol": Rol.ADMINISTRADOR, "titulo": "Administración"},
        name="login_gestion",
    ),
    path(
        "validacion/entrar/",
        views.entrar,
        {"plantilla": "personas/gestion.html", "ruta": "login_validacion",
         "rol": Rol.VALIDADOR, "titulo": "Validación"},
        name="login_validacion",
    ),
    path(
        "apoyo/entrar/",
        views.entrar,
        {"plantilla": "personas/gestion.html", "ruta": "login_apoyo",
         "rol": Rol.APOYO, "titulo": "Personal de apoyo"},
        name="login_apoyo",
    ),
    path("apoyo/", uso.bloques, name="panel_apoyo"),
    path("apoyo/checkout/<str:codigo>/", uso.checkout, name="checkout_apoyo"),
    path("configuracion/", RedirectView.as_view(pattern_name="panel_bloques")),
    path("configuracion/bloques/", agenda.bloques, name="panel_bloques"),
    path("configuracion/bloques/editar/", agenda.editar_bloque, name="editar_bloque"),
    path("configuracion/areas/", configuracion.seccion, {"pestana": "areas"}, name="panel_areas"),
    path("configuracion/reglas/", configuracion.reglas, name="panel_reglas"),
    path("admin/", admin.site.urls),
]
