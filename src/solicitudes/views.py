from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

from configuracion.models import Parametros
from personas.models import Rol

from . import validacion
from .forms import MAXIMO_ACOMPANANTES, MAXIMO_PERSONAS, AcompananteFormSet, SolicitudForm


def _revisar_acompanantes(formset, esperados, correo_solicitante):
    """Cruza las filas llenas con la cantidad de personas declarada.

    Vive fuera de los formularios porque es la unica regla que necesita ver los
    dos a la vez: `personas` esta en uno y las filas en el otro.

    Devuelve (filas_llenas, errores).
    """
    llenos = [f for f in formset.forms if f.esta_lleno]
    errores = []

    if len(llenos) != esperados:
        errores.append(
            f"Declaraste {esperados + 1} personas en sala, así que faltan los datos "
            f"de {esperados} acompañante(s); tienes {len(llenos)} completo(s)."
        )

    # US-02 AC6: si dos filas traen el mismo correo no hay identificacion que
    # valga, y el correo es lo unico que distingue a una persona de otra.
    correos = [f.cleaned_data["correo"].lower() for f in llenos if f.cleaned_data.get("correo")]
    if len(correos) != len(set(correos)):
        errores.append("Hay un correo repetido entre los acompañantes.")
    if correo_solicitante.lower() in correos:
        errores.append("Tu propio correo ya está incluido: eres parte de la cuenta de personas.")

    return llenos, errores


def _estado_inicial(form):
    """Con que valores arranca Alpine al pintar la pagina.

    Se calcula aca y no en la plantilla porque `form.data` es lo que mando el
    navegador, sin limpiar: si alguien reenvia `personas=abc`, interpolarlo tal
    cual en el `x-data` deja el JavaScript de la pagina roto.
    """
    if not form.is_bound:
        return 1, False
    try:
        personas = int(form.data.get("personas", 1))
    except (TypeError, ValueError):
        personas = 1
    return min(max(personas, 1), MAXIMO_PERSONAS), bool(form.data.get("acepta_terminos"))


def _contexto(form, formset, extra=None):
    personas_inicial, acepta_inicial = _estado_inicial(form)
    base = {
        "form": form,
        "formset": formset,
        "personas_inicial": personas_inicial,
        "acepta_inicial": acepta_inicial,
        "maximo_personas": MAXIMO_PERSONAS,
        "maximo_acompanantes": MAXIMO_ACOMPANANTES,
        # US-04 AC5: lo edita el administrador en la pestaña de reglas.
        "terminos": Parametros.cargar().terminos,
    }
    base.update(extra or {})
    return base


@login_required
def solicitar(request):
    """T4 - formulario de solicitud de reserva (US-02).

    Todavia no escribe nada: cual entidad guarda el estado de la solicitud
    —Solicitud o Ticket— es una decision de modelo que el equipo no ha cerrado.
    Cuando se cierre, lo unico que cambia aca es el bloque de exito.
    """
    areas = request.user.areas.filter(activa=True)
    if not areas.exists():
        # US-05 AC4: la solicitud se vincula a un area. Sin area no hay a que
        # vincularla, y es mejor decirlo que mostrar un desplegable vacio.
        return render(request, "solicitudes/sin_area.html")

    if request.method != "POST":
        form = SolicitudForm(usuario=request.user)
        return render(request, "solicitudes/solicitar.html", _contexto(form, AcompananteFormSet()))

    form = SolicitudForm(request.POST, usuario=request.user)
    formset = AcompananteFormSet(request.POST)

    if not (form.is_valid() and formset.is_valid()):
        return render(request, "solicitudes/solicitar.html", _contexto(form, formset))

    llenos, errores = _revisar_acompanantes(
        formset, form.cleaned_data["personas"] - 1, request.user.email
    )
    if errores:
        return render(request, "solicitudes/solicitar.html", _contexto(form, formset, {"errores": errores}))

    return render(request, "solicitudes/enviada.html", {
        "solicitud": form.cleaned_data,
        "acompanantes": [f.cleaned_data for f in llenos],
    })


def es_validador(usuario):
    return usuario.is_authenticated and usuario.tiene_rol(Rol.VALIDADOR)


@user_passes_test(es_validador, login_url="login_validacion")
def panel_validador(request):
    """Bandeja del validador, con datos de prueba mientras no exista el modelo.

    `validacion.cargar` es el unico punto que sabe de donde vienen los datos.
    """
    return render(request, "solicitudes/validador.html", {
        "datos": validacion.cargar(),
        "origen": validacion.ORIGEN,
    })
