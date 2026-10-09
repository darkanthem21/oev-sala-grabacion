from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from .forms import ParametrosForm
from .models import CambioParametro, Parametros
from .services import guardar

# El historial completo está en la administración de Django. Acá basta con lo
# último que se tocó, que es como se detecta un cambio ajeno.
ULTIMOS = 15


@staff_member_required(login_url="login_gestion")
def reglas(request):
    """Los parámetros con los que opera el sistema (US-04).

    Se guarda con POST y se vuelve con una redirección, para que recargar no
    reenvíe el formulario y duplique las filas de la bitácora. Lo que pasó va
    como aviso flotante.
    """
    parametros = Parametros.cargar()

    if request.method == "POST":
        formulario = ParametrosForm(request.POST, instance=parametros)
        if formulario.is_valid():
            cambios = len(guardar(formulario, request.user))
            if cambios:
                plural = "s" if cambios > 1 else ""
                messages.success(request, f"{cambios} cambio{plural} guardado{plural}. Rigen para las "
                                          "solicitudes nuevas; las ya enviadas no cambian.")
            else:
                messages.info(request, "No había nada que cambiar.")
            return redirect("panel_reglas")
        messages.error(request, "Corrige lo marcado en rojo. No se guardó nada.")
    else:
        formulario = ParametrosForm(instance=parametros)

    return render(request, "configuracion/reglas.html", {
        "pestana": "reglas",
        "form": formulario,
        "historial": CambioParametro.objects.select_related("quien")[:ULTIMOS],
    })


# Marcador de posición; Áreas es US-05.
@staff_member_required(login_url="login_gestion")
def seccion(request, pestana):
    return render(request, "configuracion/seccion.html", {"pestana": pestana})
