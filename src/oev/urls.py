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
from uso.checkout import views as checkout

urlpatterns = [
    path("", views.panel, name="panel"),
    path("solicitar/", include("solicitudes.urls")),
    path("validador/", solicitudes.panel_validador, name="panel_validador"),
    path("validador/resolver/", solicitudes.resolver_solicitud, name="resolver_solicitud"),
    # US-11: el validador y el administrador comparten historial, así que no
    # cuelga de /validador/ ni de /configuracion/.
    path("validacion/historial/", solicitudes.historial_validacion, name="historial_validacion"),
    path("validacion/historial/<int:solicitud_id>/", solicitudes.resolucion, name="historial_resolucion"),
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
    # clave. Lo que cambia es el título, el grupo que dejan pasar, el panel al
    # que llevan y cómo se ven: `puerta` elige el color del rol y `nombre` es lo
    # que dice el panel de la izquierda.
    path(
        "solicitante/entrar/",
        views.entrar,
        {"ruta": "login_solicitante", "rol": Rol.SOLICITANTE, "destino": "solicitar",
         "titulo": "Ingreso de solicitantes", "puerta": "solicitante", "nombre": "Solicitantes"},
        name="login_solicitante",
    ),
    path(
        "configuracion/entrar/",
        views.entrar,
        {"ruta": "login_gestion", "rol": Rol.ADMINISTRADOR, "destino": "panel_bloques",
         "titulo": "Ingreso de administración", "puerta": "gestion", "nombre": "Administración"},
        name="login_gestion",
    ),
    path(
        "validacion/entrar/",
        views.entrar,
        {"ruta": "login_validacion", "rol": Rol.VALIDADOR, "destino": "panel_validador",
         "titulo": "Ingreso de validadores", "puerta": "validacion", "nombre": "Validación"},
        name="login_validacion",
    ),
    path(
        "apoyo/entrar/",
        views.entrar,
        {"ruta": "login_apoyo", "rol": Rol.APOYO, "destino": "panel_apoyo",
         "titulo": "Ingreso del personal de apoyo", "puerta": "apoyo", "nombre": "Personal de apoyo"},
        name="login_apoyo",
    ),
    path("apoyo/", uso.bloques, name="panel_apoyo"),
    path("apoyo/checkout/<str:codigo>/", checkout.checkout, name="checkout_apoyo"),
    path("apoyo/evidencia/<int:pk>/", checkout.foto_integridad, name="foto_integridad"),
    path("configuracion/checkout/", checkout.editor_checkout, name="panel_checkout"),
    path("configuracion/", RedirectView.as_view(pattern_name="panel_bloques")),
    path("configuracion/bloques/", agenda.bloques, name="panel_bloques"),
    path("configuracion/bloques/editar/", agenda.editar_bloque, name="editar_bloque"),
    path("configuracion/bloqueos/", agenda.editar_bloqueo, name="editar_bloqueo"),
    path("configuracion/areas/", views.areas, name="panel_areas"),
    path("configuracion/usuarios/", views.usuarios, name="panel_usuarios"),
    path("configuracion/usuarios/nueva/", views.usuario, name="panel_usuario_nuevo"),
    path("configuracion/usuarios/cargar/", views.cargar_usuarios, name="panel_usuarios_cargar"),
    path("configuracion/usuarios/plantilla.csv", views.plantilla_usuarios, name="panel_usuarios_plantilla"),
    path("configuracion/usuarios/<int:pk>/", views.usuario, name="panel_usuario"),
    path("configuracion/reglas/", configuracion.reglas, name="panel_reglas"),
    path("configuracion/validacion/", solicitudes.panel_validacion_admin, name="panel_validacion"),
    # US-12: la pestaña la sirve `uso`, porque cuenta check-outs; la dirección y
    # el nombre son los de US-10, para no romper enlaces.
    path("configuracion/sanciones/", uso.sanciones, name="panel_sanciones"),
    path("configuracion/sanciones/<int:usuario_id>/", uso.sanciones_de, name="sanciones_de"),
    path("admin/", admin.site.urls),
]
