from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from configuracion.models import Parametros

from . import carga, services
from .forms import AreaForm, LevantarSancionForm, UsuarioForm
from .models import PUERTA_DEL_ROL, Area, CambioArea, CambioUsuario, Rol, Sancion, Usuario
from .permisos import solo_administradores

# Como en Reglas: el registro completo está en /admin/, y acá basta lo último.
ULTIMOS_CAMBIOS = 15
CUENTAS_POR_PAGINA = 50


def destino_tras_login(usuario):
    """A qué panel lleva la raíz `/` a alguien ya autenticado. Tras entrar
    manda la puerta (`destino`), no esto.

    US-01 AC3 dice "panel principal de reservas": para el solicitante es el
    formulario de US-02.

    Los roles ya son grupos de Django (US-08 AC6), así que alguien puede tener
    varios: el orden de abajo es la prioridad, no una clasificación. `is_staff`
    sigue contando como administrador porque el superusuario que crea el
    despliegue no pertenece a ningún grupo.
    """
    if usuario.is_staff or usuario.tiene_rol(Rol.ADMINISTRADOR):
        return reverse("panel_bloques")
    if usuario.tiene_rol(Rol.VALIDADOR):
        return reverse("panel_validador")
    if usuario.tiene_rol(Rol.APOYO):
        return reverse("panel_apoyo")
    return reverse("solicitar")


def _con_error(request, form, ruta):
    """AC4: el mismo texto para clave mala, correo inexistente, cuenta sin el rol
    de la puerta y cuenta bloqueada. Cualquier diferencia le regalaría al atacante
    la lista de cuentas. La regla del bloqueo (AC5) va en el texto para que quien
    quedó bloqueado entienda por qué no entra."""
    parametros = Parametros.cargar()
    mensaje = (
        f"Correo o contraseña incorrectos. Tras {parametros.intentos_maximos} intentos "
        f"seguidos la cuenta se bloquea {parametros.minutos_bloqueo} minutos."
    )
    return render(
        request,
        "personas/_formulario_ingreso.html",
        {"form": form, "error": mensaje, "ruta": ruta, "next": request.POST.get("next", "")},
    )


def _registrar_fallo(usuario):
    """AC5: unos cuantos fallos seguidos bloquean la cuenta, temporalmente.

    Cuántos y por cuánto los fija el administrador desde el panel (US-04).
    """
    parametros = Parametros.cargar()
    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= parametros.intentos_maximos:
        usuario.bloqueado_hasta = timezone.now() + timedelta(minutes=parametros.minutos_bloqueo)
        usuario.intentos_fallidos = 0
    usuario.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])


def _puede_pasar(usuario, rol):
    """Quién cruza esta puerta.

    En la de administración vale también `is_staff`, porque el superusuario del
    despliegue no pertenece a ningún grupo y quedaría afuera de su propia puerta.
    """
    if rol == Rol.ADMINISTRADOR and usuario.is_staff:
        return True
    return usuario.tiene_rol(rol)


def entrar(request, rol, destino, ruta, titulo, puerta, nombre):
    """Las puertas del sistema. Cada una cambia el título, a quién deja pasar, a
    qué panel lo lleva (`destino`, nombre de URL) y su panel de color (`puerta`
    y `nombre`). La plantilla, la autenticación, el bloqueo por intentos y la
    recuperación de clave son las mismas para todas."""
    contexto = {"form": AuthenticationForm(), "ruta": ruta, "titulo": titulo, "next": request.GET.get("next", ""),
                "puerta": puerta, "nombre": nombre}
    if request.method != "POST":
        return render(request, "personas/login.html", contexto)

    form = AuthenticationForm(request, data=request.POST)
    usuario = Usuario.objects.filter(email__iexact=request.POST.get("username", "")).first()
    # Se revisa la clave aunque la cuenta esté bloqueada: si no, la respuesta
    # rápida (sin calcular el hash) delataría qué cuentas existen.
    valido = form.is_valid()

    if usuario and usuario.esta_bloqueado:
        return _con_error(request, form, ruta)

    if valido:
        entrante = form.get_user()
        # Una puerta de rol no responde "no eres administrador". Ese mensaje la
        # convertiría en un oráculo para saber qué correos existen y cuáles
        # mandan, así que contesta lo mismo que una clave mala, y sin sesión.
        if not _puede_pasar(entrante, rol):
            return _con_error(request, form, ruta)
        if entrante.intentos_fallidos or entrante.bloqueado_hasta:
            entrante.intentos_fallidos = 0
            entrante.bloqueado_hasta = None
            entrante.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
        login(request, entrante)
        # Vuelve a la página que pidió el ingreso (p. ej. el enlace de
        # confirmación del correo), solo si es de este sitio.
        siguiente = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(siguiente, {request.get_host()}, request.is_secure()):
            siguiente = reverse(destino)
        # 204 sin cuerpo porque no hay nada que pegar; el navegador navega.
        return HttpResponse(status=204, headers={"HX-Redirect": siguiente})

    if usuario:
        _registrar_fallo(usuario)
    return _con_error(request, form, ruta)


@login_required
def panel(request):
    """La raíz lleva a cada uno a su panel, por la prioridad de sus roles."""
    return redirect(destino_tras_login(request.user))


@solo_administradores
def sanciones(request):
    """US-10: las sanciones vigentes, para que el administrador las levante.

    Crearlas y acortarlas es del superusuario, en la administración de Django;
    el historial completo también está ahí. Levantar va por POST y vuelve con
    una redirección, para que recargar no lo intente dos veces.
    """
    if request.method == "POST":
        sancion = get_object_or_404(Sancion, pk=request.POST.get("sancion"))
        formulario = LevantarSancionForm(request.POST)
        if not formulario.is_valid():
            messages.error(request, " ".join(formulario.errors["motivo"]))
            return redirect("panel_sanciones")
        try:
            services.levantar(sancion, request.user, formulario.cleaned_data["motivo"])
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            persona = sancion.usuario.get_full_name() or sancion.usuario.email
            messages.success(request, f"Levantaste la sanción de {persona}. Ya puede solicitar la sala.")
        return redirect("panel_sanciones")

    return render(request, "personas/sanciones.html", {
        "pestana": "sanciones",
        "vigentes": Sancion.objects.vigentes().select_related("usuario", "creada_por").order_by("termino", "id"),
    })


@solo_administradores
def areas(request):
    """US-05: las áreas con su nota y cuánta gente tiene cada una.

    Crear, editar, desactivar y reactivar van por POST y vuelven con una
    redirección, como Sanciones; lo que pasó llega como aviso flotante. Las
    personas se asignan a un área desde la pestaña Usuarios (US-08).
    """
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion not in ("crear", "editar", "desactivar", "reactivar"):
            return HttpResponseBadRequest()
        area = None if accion == "crear" else get_object_or_404(Area, pk=request.POST.get("area"))

        if accion in ("desactivar", "reactivar"):
            if not services.cambiar_estado(area, accion == "reactivar", request.user):
                messages.info(request, f"«{area}» ya estaba {'activa' if accion == 'reactivar' else 'inactiva'}.")
            elif accion == "desactivar":
                messages.success(request, f"Desactivaste «{area}». Ya no se ofrece al pedir; las solicitudes "
                                          "que la usan no cambian.")
            else:
                messages.success(request, f"Reactivaste «{area}». Vuelve a ofrecerse al pedir.")
            return redirect("panel_areas")

        formulario = AreaForm(request.POST, instance=area)
        if not formulario.is_valid():
            errores = " ".join(e for lista in formulario.errors.values() for e in lista)
            messages.error(request, f"{errores} No se guardó nada.")
        elif not formulario.has_changed():
            messages.info(request, "No había nada que cambiar.")
        else:
            area = services.guardar_area(formulario, request.user)
            messages.success(request, f"Creaste el área «{area}»." if accion == "crear" else f"Guardaste «{area}».")
        return redirect("panel_areas")

    return render(request, "personas/areas.html", {
        "pestana": "areas",
        "areas": Area.objects.annotate(cuantos=Count("usuarios")).order_by("-activa", "nombre"),
        "historial": CambioArea.objects.select_related("area", "quien")[:ULTIMOS_CAMBIOS],
    })


ESTADOS = {"activas": Q(is_active=True), "desactivadas": Q(is_active=False)}


def _roles_de(cuenta):
    """Sus roles en el orden de `Rol`, con la puerta que elige ícono y color (AC7)."""
    tiene = {grupo.name for grupo in cuenta.groups.all()}
    return [(PUERTA_DEL_ROL[rol], rol.label) for rol in Rol if rol in tiene]


@solo_administradores
def usuarios(request):
    """US-08 AC1: las cuentas con roles, áreas y estado, con búsqueda y filtros.
    Crear y editar tienen su página, para mostrar cada error junto a su campo."""
    filtros = {clave: request.GET.get(clave, "").strip() for clave in ("q", "rol", "area", "estado")}
    cuentas = Usuario.objects.prefetch_related(
        "groups", Prefetch("areas", queryset=Area.objects.order_by("nombre")),
    ).order_by("-is_active", "first_name", "last_name", "email")
    # Cada palabra en cualquiera de los tres campos, para que «ana pérez» encuentre
    # a Ana Pérez aunque nombre y apellido estén separados.
    for termino in filtros["q"].split():
        cuentas = cuentas.filter(
            Q(email__icontains=termino) | Q(first_name__icontains=termino) | Q(last_name__icontains=termino)
        )
    if filtros["rol"] in Rol.values:
        cuentas = cuentas.filter(groups__name=filtros["rol"])
    if filtros["area"].isdigit():
        cuentas = cuentas.filter(areas__pk=filtros["area"])
    if filtros["estado"] in ESTADOS:
        cuentas = cuentas.filter(ESTADOS[filtros["estado"]])

    pagina = Paginator(cuentas, CUENTAS_POR_PAGINA).get_page(request.GET.get("pagina"))
    for cuenta in pagina:
        cuenta.lista_roles = _roles_de(cuenta)
    sin_pagina = request.GET.copy()
    sin_pagina.pop("pagina", None)
    return render(request, "personas/usuarios.html", {
        "pestana": "usuarios",
        "pagina": pagina,
        "filtros": filtros,
        "filtrando": any(filtros.values()),
        "url_pagina": f"?{sin_pagina.urlencode()}&pagina=" if sin_pagina else "?pagina=",
        "roles": Rol.choices,
        "areas": Area.objects.order_by("-activa", "nombre"),
        "historial": CambioUsuario.objects.select_related("usuario", "quien")[:ULTIMOS_CAMBIOS],
    })


@solo_administradores
def usuario(request, pk=None):
    """US-08 AC2 a AC4: crear o editar una cuenta, desactivarla o reactivarla y
    reenviarle el correo para crear su contraseña."""
    cuenta = get_object_or_404(Usuario, pk=pk) if pk else Usuario()
    nombre = cuenta.get_full_name() or cuenta.email
    da_admin = request.user.is_superuser
    form = UsuarioForm(instance=cuenta, da_admin=da_admin)

    if request.method == "POST":
        accion = request.POST.get("accion")
        if pk and accion in ("desactivar", "reactivar"):
            try:
                cambio = services.cambiar_estado_de_cuenta(cuenta, accion == "reactivar", request.user)
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
            else:
                if not cambio:
                    estado = "activa" if accion == "reactivar" else "desactivada"
                    messages.info(request, f"La cuenta de {nombre} ya estaba {estado}.")
                elif accion == "desactivar":
                    messages.success(request, f"Desactivaste la cuenta de {nombre}. Ya no puede entrar; "
                                              "su historial se conserva.")
                else:
                    messages.success(request, f"Reactivaste la cuenta de {nombre}. Puede volver a entrar "
                                              "con su contraseña.")
            return redirect("panel_usuario", pk=pk)

        if pk and accion == "reenviar":
            if not services.puede_cambiar_cuenta(cuenta, request.user):
                messages.error(request, "Solo el superusuario cambia la cuenta de otro administrador.")
            elif not cuenta.is_active:
                messages.error(request, "La cuenta está desactivada: reactívala antes de reenviar el correo.")
            elif services.enviar_acceso(cuenta):
                messages.success(request, f"Le reenviaste a {cuenta.email} el correo para crear su contraseña.")
            else:
                messages.error(request, "El correo no salió. Inténtalo de nuevo en unos minutos.")
            return redirect("panel_usuario", pk=pk)

        if accion != "guardar":
            return HttpResponseBadRequest()
        form = UsuarioForm(request.POST, instance=cuenta, da_admin=da_admin)
        if pk and not form.has_changed():
            messages.info(request, "No había nada que cambiar.")
            return redirect("panel_usuarios")
        if form.is_valid():
            try:
                cuenta = services.guardar_usuario(form, request.user)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                guardada = cuenta.get_full_name() or cuenta.email
                if pk:
                    messages.success(request, f"Guardaste la cuenta de {guardada}.")
                elif services.enviar_acceso(cuenta):
                    messages.success(request, f"Creaste la cuenta de {guardada}. Le llegará un correo a "
                                              f"{cuenta.email} para crear su contraseña.")
                else:
                    messages.error(request, f"Creaste la cuenta de {guardada}, pero el correo no salió. "
                                            "Reenvíalo desde su cuenta.")
                return redirect("panel_usuarios")

    return render(request, "personas/usuario.html", {
        "pestana": "usuarios",
        "form": form,
        "cuenta": cuenta,
        "nombre": nombre,
        "roles": [
            (rol.value, rol.label, PUERTA_DEL_ROL[rol]) for rol in Rol if da_admin or rol != Rol.ADMINISTRADOR
        ],
        "bloqueada": not services.puede_cambiar_cuenta(cuenta, request.user),
        "solicitante": Rol.SOLICITANTE in (form["roles"].value() or []),
        # AC5: lo que sigue abierto, para avisarlo antes de desactivar.
        "en_curso": cuenta.solicitudes.en_curso(timezone.localdate()) if cuenta.pk and cuenta.is_active else {},
    })


SESION_CARGA = "carga_de_usuarios"


@solo_administradores
def plantilla_usuarios(request):
    """AC8: la planilla vacía, con las columnas que lee la carga."""
    respuesta = HttpResponse(carga.plantilla(), content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="cuentas-oev.csv"'
    return respuesta


@solo_administradores
def cargar_usuarios(request):
    """AC8 y AC9: subir la planilla, ver fila por fila qué pasaría y confirmar.
    Lo leído espera en la sesión entre la vista previa y la confirmación; al
    confirmar se revisa de nuevo contra la base, por si algo cambió entremedio."""
    contexto = {"pestana": "usuarios", "columnas": carga.COLUMNAS, "roles": Rol.choices,
                "areas": Area.objects.filter(activa=True).order_by("nombre")}
    accion = request.POST.get("accion")

    if accion == "confirmar":
        crudas = request.session.pop(SESION_CARGA, None)
        if not crudas:
            messages.error(request, "Vuelve a subir la planilla: la vista previa ya no está.")
            return redirect("panel_usuarios_cargar")
        try:
            resultado = carga.aplicar(crudas, request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect("panel_usuarios_cargar")
        partes = []
        if resultado["creadas"]:
            n = resultado["creadas"]
            partes.append(f"creaste {n} cuenta{'s' if n != 1 else ''}")
        if resultado["actualizadas"]:
            n = resultado["actualizadas"]
            partes.append(f"actualizaste {n}")
        messages.success(request, (" y ".join(partes) or "No había nada que cambiar").capitalize() + ".")
        if resultado["sin_correo"]:
            messages.error(request, "No salió el correo para crear la contraseña a: "
                                    f"{', '.join(resultado['sin_correo'])}. Reenvíalo desde cada cuenta.")
        return redirect("panel_usuarios")

    if accion == "revisar":
        archivo = request.FILES.get("planilla")
        if archivo is None:
            contexto["error"] = "Elige el archivo de la planilla."
        else:
            try:
                crudas = carga.leer(archivo.read(carga.MAX_BYTES + 1))
            except ValidationError as error:
                contexto["error"] = " ".join(error.messages)
            else:
                filas = carga.revisar(crudas, request.user)
                errores = sum(1 for f in filas if f.errores)
                if errores:
                    request.session.pop(SESION_CARGA, None)
                else:
                    request.session[SESION_CARGA] = crudas
                contexto |= {
                    "filas": filas, "nombre_archivo": archivo.name, "con_errores": errores,
                    "crear": sum(1 for f in filas if f.accion == "crear"),
                    "actualizar": sum(1 for f in filas if f.accion == "actualizar"),
                }
    return render(request, "personas/cargar_usuarios.html", contexto)
