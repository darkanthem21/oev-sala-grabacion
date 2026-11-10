"""Pantallas del editor, el reporte y la descarga de evidencias del check-out."""

import json
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from solicitudes.models import SolicitudBloque
from .. import services as bloques_services
from .forms import AsistenciaForm, CheckoutForm, EditorCheckoutForm
from .models import Checkout, FotoIntegridad, FormularioCheckout
from .historial import historial_semanal, registros_recientes
from .permissions import es_administrador, es_apoyo, puede_consultar
from .services import casos_falta_integridad, guardar_reporte, resumen_respuestas


@user_passes_test(es_apoyo, login_url="login_apoyo")
def checkout(request, codigo):
    """Asistencia previa; solo quienes asistieron requieren revisión de la sala."""
    bloque = bloques_services.buscar(codigo)
    if bloque is None or bloque["checkout"] is None:
        raise Http404
    volver = f"{reverse('panel_apoyo')}?fecha={bloque['fecha']:%Y-%m-%d}"

    registro = Checkout.objects.filter(ticket_id=int(codigo[2:])).select_related("registrado_por", "editado_por").first()
    asistencia = AsistenciaForm(request.POST if request.method == "POST" else None)
    formulario = None
    mostrar_listado = False
    if request.method == "POST" and registro:
        return redirect(volver)
    if request.method == "POST" and asistencia.is_valid():
        FormularioCheckout.cargar()
        with transaction.atomic():
            # Serializa envíos del mismo ticket y la publicación del listado.
            ticket = SolicitudBloque.objects.select_for_update().get(pk=int(codigo[2:]))
            listado = FormularioCheckout.objects.select_for_update().get(pk=1)
            if Checkout.objects.filter(ticket=ticket).exists():
                return redirect(volver)
            actual = bloques_services.buscar(codigo)
            if actual is None or actual["checkout"] != "pendiente":
                raise Http404
            if asistencia.cleaned_data["asistencia"] == "no":
                guardar_reporte(ticket, listado, {}, request.user, asistio=False)
                messages.success(request, "Inasistencia registrada. No se requiere revisión de la sala.")
                return redirect(volver)
            mostrar_listado = True
            continuar = request.POST.get("accion") == "asistencia"
            formulario = CheckoutForm(None if continuar else request.POST, None if continuar else request.FILES, listado=listado)
            if not continuar and formulario.is_valid():
                guardar_reporte(ticket, listado, formulario.cleaned_data, request.user)
                messages.success(request, "Check-out registrado con sus respuestas y evidencias.")
                return redirect(volver)
        if formulario.is_bound:
            messages.error(request, "Revisa los campos indicados. Si adjuntaste fotos, vuelve a seleccionarlas antes de enviar.")

    return render(request, "uso/checkout/reporte.html", {
        "bloque": bloque, "registro": registro, "volver": volver, "form": formulario,
        "asistencia_form": asistencia, "mostrar_listado": mostrar_listado,
        "resumen": resumen_respuestas(registro), "puede_editar": registro.puede_editar(request.user) if registro else False,
    })


@user_passes_test(es_apoyo, login_url="login_apoyo")
def editar_checkout(request, codigo):
    bloque = bloques_services.buscar(codigo)
    if bloque is None or bloque["checkout"] != "completado":
        raise Http404
    with transaction.atomic():
        registro = get_object_or_404(Checkout.objects.select_for_update(), ticket_id=int(codigo[2:]))
        if not registro.puede_editar(request.user):
            raise PermissionDenied("Solo el autor puede editar durante los 10 minutos posteriores al registro.")
        listado = SimpleNamespace(secciones=registro.formulario, revision=registro.revision)
        asistencia = AsistenciaForm(
            request.POST if request.method == "POST" else None,
            initial={"asistencia": "si" if registro.asistio else "no"},
        )
        mostrar_listado = registro.asistio
        validar_listado = False
        if request.method == "POST" and asistencia.is_valid():
            mostrar_listado = asistencia.cleaned_data["asistencia"] == "si"
            if not mostrar_listado:
                guardar_reporte(registro.ticket, listado, {}, request.user, asistio=False, registro=registro)
                messages.success(request, "Check-out editado: inasistencia registrada.")
                return redirect("checkout_apoyo", codigo=codigo)
            if request.POST.get("accion") != "asistencia":
                validar_listado = True
        formulario = CheckoutForm(
            request.POST if validar_listado else None, request.FILES if validar_listado else None,
            listado=listado, registro=registro,
        )
        if validar_listado:
            if formulario.is_valid():
                guardar_reporte(registro.ticket, listado, formulario.cleaned_data, request.user, registro=registro)
                messages.success(request, "Check-out editado.")
                return redirect("checkout_apoyo", codigo=codigo)
            messages.error(request, "Revisa lo indicado. Las fotografías ya registradas se conservan si no adjuntas otras.")
    return render(request, "uso/checkout/editar.html", {
        "bloque": bloque, "registro": registro, "asistencia_form": asistencia,
        "form": formulario, "mostrar_listado": mostrar_listado,
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


@user_passes_test(es_administrador, login_url="login_gestion")
def historial_checkout(request):
    return render(request, "uso/checkout/historial.html", {
        "pestana": "checkout", "checkout_pestana": "historial",
        **historial_semanal(request.GET.get("semana"), request.GET.get("pagina")),
    })


@user_passes_test(es_administrador, login_url="login_gestion")
def pdf_checkout(request, pk):
    from .pdf import generar_pdf

    registro = get_object_or_404(registros_recientes().prefetch_related("fotos"), pk=pk)
    return FileResponse(generar_pdf(registro), content_type="application/pdf", filename=f"checkout-{registro.ticket.ticket}.pdf")


@user_passes_test(es_administrador, login_url="login_gestion")
def preview_checkout(request):
    """Prueba un borrador con las mismas reglas del check-out, sin persistirlo."""
    probado = request.method == "POST" and request.POST.get("accion") == "probar"
    if request.method == "POST":
        editor = EditorCheckoutForm(request.POST)
        if not editor.is_valid():
            return render(request, "uso/checkout/editor.html", {
                "pestana": "checkout", "form": editor, "listado": FormularioCheckout.cargar(),
            })
        listado = SimpleNamespace(**editor.cleaned_data)
    else:
        listado = FormularioCheckout.cargar()
    asistencia = AsistenciaForm(request.POST if request.method == "POST" and (probado or request.POST.get("accion") == "asistencia") else None)
    asistencia_valida = asistencia.is_valid() if asistencia.is_bound else False
    mostrar_listado = asistencia_valida and asistencia.cleaned_data["asistencia"] == "si"
    formulario = CheckoutForm(request.POST if probado and mostrar_listado else None, request.FILES if probado and mostrar_listado else None, listado=listado)
    return render(request, "uso/checkout/preview.html", {
        "pestana": "checkout", "form": formulario, "probado": probado,
        "asistencia_form": asistencia, "mostrar_listado": mostrar_listado,
        "inasistencia": asistencia_valida and not mostrar_listado,
        "validado": bool(probado and asistencia_valida and (not mostrar_listado or formulario.is_valid())),
        "secciones_json": json.dumps(listado.secciones, ensure_ascii=False),
    })


@user_passes_test(puede_consultar, login_url="login_apoyo")
def foto_integridad(request, pk):
    foto = get_object_or_404(FotoIntegridad, pk=pk)
    return FileResponse(foto.archivo.open("rb"), as_attachment=True)


@user_passes_test(puede_consultar, login_url="login_apoyo")
def foto_cierre(request, pk):
    registro = get_object_or_404(Checkout, pk=pk)
    if not registro.foto_final:
        raise Http404
    return FileResponse(registro.foto_final.open("rb"), as_attachment=True)


@user_passes_test(puede_consultar, login_url="login_apoyo")
def reporte_integridad(request, codigo):
    bloque = bloques_services.buscar(codigo)
    if bloque is None or bloque["checkout"] != "completado":
        raise Http404
    registro = get_object_or_404(Checkout, ticket_id=int(codigo[2:]))
    return render(request, "uso/checkout/incidencias.html", {
        "bloque": bloque, "registro": registro, "casos": casos_falta_integridad(registro),
    })
