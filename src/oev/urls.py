from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path

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
    path("admin/", admin.site.urls),
]
