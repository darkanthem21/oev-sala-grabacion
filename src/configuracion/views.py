from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import ParametrosForm
from .models import CambioParametro, Parametros
from .services import guardar

# El historial completo está en la administración de Django. Acá basta con lo
# último que se tocó, que es como se detecta un cambio ajeno.
ULTIMOS = 15


def _guardados(valor):
    """Llega de la barra de direcciones, así que puede ser cualquier cosa."""
    try:
        return max(0, int(valor))
    except (TypeError, ValueError):
        return None


@staff_member_required(login_url="login_gestion")
def reglas(request):
    """Los parámetros con los que opera el sistema (US-04).

    Se guarda con POST y se vuelve con una redirección, para que recargar no
    reenvíe el formulario y duplique las filas de la bitácora.
    """
    parametros = Parametros.cargar()

    if request.method == "POST":
        formulario = ParametrosForm(request.POST, instance=parametros)
        if formulario.is_valid():
            cambios = guardar(formulario, request.user)
            return redirect(f"{reverse('panel_reglas')}?guardados={len(cambios)}")
    else:
        formulario = ParametrosForm(instance=parametros)

    return render(request, "configuracion/reglas.html", {
        "pestana": "reglas",
        "form": formulario,
        "historial": CambioParametro.objects.select_related("quien")[:ULTIMOS],
        "guardados": _guardados(request.GET.get("guardados")),
    })


# Marcador de posición; Áreas es US-05.
@staff_member_required(login_url="login_gestion")
def seccion(request, pestana):
    return render(request, "configuracion/seccion.html", {"pestana": pestana})
