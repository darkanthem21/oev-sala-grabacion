"""Pantallas del editor, el reporte y la descarga de evidencias del check-out."""

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from solicitudes.models import SolicitudBloque
from .. import services as bloques_services
from .forms import CheckoutForm, EditorCheckoutForm
from .models import Checkout, FotoIntegridad, FormularioCheckout
from .permissions import es_administrador, es_apoyo
from .services import guardar_reporte


@user_passes_test(es_apoyo, login_url="login_apoyo")
def checkout(request, codigo):
    """Revisión del bloque terminado, con evidencia obligatoria ante un No."""
    bloque = bloques_services.buscar(codigo)
    if bloque is None or bloque["checkout"] is None:
        raise Http404
    volver = f"{reverse('panel_apoyo')}?fecha={bloque['fecha']:%Y-%m-%d}"

    listado = FormularioCheckout.cargar()
    formulario = CheckoutForm(listado=listado)
    if request.method == "POST":
        with transaction.atomic():
            # Serializa envíos del mismo ticket y la publicación del listado.
            ticket = SolicitudBloque.objects.select_for_update().get(pk=int(codigo[2:]))
            listado = FormularioCheckout.objects.select_for_update().get(pk=1)
            if Checkout.objects.filter(ticket=ticket).exists():
                return redirect(volver)
            actual = bloques_services.buscar(codigo)
            if actual is None or actual["checkout"] != "pendiente":
                raise Http404
            formulario = CheckoutForm(request.POST, request.FILES, listado=listado)
            if formulario.is_valid():
                guardar_reporte(ticket, listado, formulario.cleaned_data, request.user)
                messages.success(request, "Check-out registrado con sus respuestas y evidencias.")
                return redirect(volver)
        messages.error(request, "Revisa los campos indicados. Si adjuntaste fotos, vuelve a seleccionarlas antes de enviar.")

    registro = Checkout.objects.filter(ticket_id=int(codigo[2:])).select_related("registrado_por").first()
    resumen = []
    if registro:
        fotos = {foto.pregunta: foto for foto in registro.fotos.all()}
        for seccion in registro.formulario:
            resumen.append({"titulo": seccion["titulo"], "preguntas": [
                {**pregunta, **registro.respuestas[pregunta["id"]], "foto": fotos.get(pregunta["id"])}
                for pregunta in seccion["preguntas"]
            ]})
    return render(request, "uso/checkout/reporte.html", {
        "bloque": bloque,
        "registro": registro,
        "volver": volver,
        "form": formulario,
        "resumen": resumen,
    })


@user_passes_test(es_administrador, login_url="login_gestion")
def editor_checkout(request):
    listado = FormularioCheckout.cargar()
    formulario = EditorCheckoutForm(request.POST if request.method == "POST" else None, initial={"secciones": listado.secciones, "revision": listado.revision})
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            listado = FormularioCheckout.objects.select_for_update().get(pk=1)
            if formulario.cleaned_data["revision"] != listado.revision:
                formulario.add_error(None, "Otro administrador modificó el listado. Recarga antes de publicar tus cambios.")
            else:
                listado.secciones = formulario.cleaned_data["secciones"]
                listado.revision += 1
                listado.actualizado_por = request.user
                listado.save()
                messages.success(request, "Listado publicado. Los reportes completados conservan sus preguntas originales.")
                return redirect("panel_checkout")
    return render(request, "uso/checkout/editor.html", {"pestana": "checkout", "form": formulario, "listado": listado})


@user_passes_test(lambda u: es_apoyo(u) or es_administrador(u), login_url="login_apoyo")
def foto_integridad(request, pk):
    foto = get_object_or_404(FotoIntegridad, pk=pk)
    return FileResponse(foto.archivo.open("rb"), as_attachment=True)
