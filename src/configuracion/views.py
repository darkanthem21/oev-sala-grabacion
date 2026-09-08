from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


# Marcador de posicion de las pestañas que todavia no tienen contenido. Areas es
# US-05 y Reglas espera a que se zanje como se modelan los parametros.
@staff_member_required(login_url="login_gestion")
def seccion(request, pestana):
    return render(request, "configuracion/seccion.html", {"pestana": pestana})
