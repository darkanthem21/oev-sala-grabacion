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
    path("validador/resolver/", solicitudes.resolver_solicitud, name="resolver_solicitud"),
    # La puerta del solicitante vivió acá; se redirige para no romper enlaces.
    path("login/", RedirectView.as_view(pattern_name="login_solicitante", permanent=True)),
    path("logout/", auth.LogoutView.as_view(next_page="login_solicitante"), name="logout"),
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
    # US-08 AC4: una puerta por rol, todas en `<rol>/entrar/`. Solo la del
    # solicitante se enlaza desde el sitio público. Todas reusan `entrar`, así que
    # comparten plantilla, autenticación, bloqueo por intentos y recuperación de
    # clave. Lo que cambia es el título, el grupo que dejan pasar y el panel al
    # que llevan.
    path(
        "solicitante/entrar/",
        views.entrar,
        {"ruta": "login_solicitante", "rol": Rol.SOLICITANTE, "destino": "solicitar",
         "titulo": "Ingreso de solicitantes"},
        name="login_solicitante",
    ),
    path(
        "configuracion/entrar/",
        views.entrar,
        {"ruta": "login_gestion", "rol": Rol.ADMINISTRADOR, "destino": "panel_bloques",
         "titulo": "Ingreso de administración"},
        name="login_gestion",
    ),
    path(
        "validacion/entrar/",
        views.entrar,
        {"ruta": "login_validacion", "rol": Rol.VALIDADOR, "destino": "panel_validador",
         "titulo": "Ingreso de validadores"},
        name="login_validacion",
    ),
    path(
        "apoyo/entrar/",
        views.entrar,
        {"ruta": "login_apoyo", "rol": Rol.APOYO, "destino": "panel_apoyo",
         "titulo": "Ingreso del personal de apoyo"},
        name="login_apoyo",
    ),
    path("apoyo/", uso.bloques, name="panel_apoyo"),
    path("apoyo/checkout/<str:codigo>/", uso.checkout, name="checkout_apoyo"),
    path("configuracion/", RedirectView.as_view(pattern_name="panel_bloques")),
    path("configuracion/bloques/", agenda.bloques, name="panel_bloques"),
    path("configuracion/bloques/editar/", agenda.editar_bloque, name="editar_bloque"),
    path("configuracion/bloqueos/", agenda.editar_bloqueo, name="editar_bloqueo"),
    path("configuracion/areas/", configuracion.seccion, {"pestana": "areas"}, name="panel_areas"),
    path("configuracion/reglas/", configuracion.reglas, name="panel_reglas"),
    path("configuracion/validacion/", solicitudes.panel_validacion_admin, name="panel_validacion"),
    path("admin/", admin.site.urls),
]
