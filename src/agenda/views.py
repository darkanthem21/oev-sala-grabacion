import calendar
from collections import Counter
from datetime import date, time, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db.models.functions import Coalesce
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from . import services
from .forms import MODOS, BloqueForm, BloqueoForm, LevantarForm
from .models import JORNADA_MINIMA, Bloque, Bloqueo, Dia, Motivo, bloqueos_por_fecha, minutos, plantilla_semanal

# Cuántas acciones muestra el registro de bloqueos. El historial completo está
# en la administración de Django, igual que el de los parámetros.
ULTIMOS = 15

# Cuántas semanas hacia adelante ofrece la vista semanal para bloquear un bloque.
# Más lejos se bloquea desde la mensual.
SEMANAS_PARA_BLOQUEAR = 12


def _fecha(texto, por_defecto):
    """La fecha llega por la barra de direcciones y cualquiera puede escribirla."""
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return por_defecto


def _semana(dia):
    lunes = dia - timedelta(days=dia.weekday())
    return [lunes + timedelta(days=n) for n in range(5)]


def _mes(dia):
    """Las semanas del mes, recortadas a lunes-viernes (US-02 AC7)."""
    semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(dia.year, dia.month)
    return [[d for d in semana if d.weekday() < 5] for semana in semanas]


def _correr(dia, vista, signo):
    if vista == "semana":
        return dia + timedelta(days=7 * signo)
    if signo < 0:
        return (dia.replace(day=1) - timedelta(days=1)).replace(day=1)
    return (dia.replace(day=28) + timedelta(days=4)).replace(day=1)


def _titulo(vista, foco):
    """Qué se está mirando, escrito como lo diría una persona.

    La semanal dice qué semana es porque desde ahí se bloquea una fecha (US-17).
    Que los horarios valen para todas las semanas lo dice el aviso de la
    rejilla: sin él, "5 al 9 de octubre" haría creer que lo editado vale solo
    para esos cinco días.
    """
    if vista == "mes":
        return date_format(foco, "F Y").capitalize()
    lunes, viernes = _semana(foco)[0], _semana(foco)[-1]
    hasta = date_format(viernes, r"j \d\e F \d\e Y")
    if lunes.month == viernes.month:
        return f"Semana del {lunes.day} al {hasta}"
    desde = date_format(lunes, r"j \d\e F")
    return f"Semana del {desde} al {hasta}"


def _mini(foco, hoy):
    """El mes de `foco` para el mini calendario de la vista semanal.

    Lleva sábado y domingo para que se lea como un calendario cualquiera; un
    clic en ellos lleva a su semana, igual que en un día hábil.
    """
    lunes = foco - timedelta(days=foco.weekday())
    semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(foco.year, foco.month)
    return {
        "titulo": date_format(foco, "F Y").capitalize(),
        "semanas": [
            [{"fecha": d, "fuera": d.month != foco.month, "hoy": d == hoy,
              "elegida": lunes <= d < lunes + timedelta(days=7)} for d in semana]
            for semana in semanas
        ],
        "anterior": _correr(foco, "mes", -1),
        "siguiente": _correr(foco, "mes", +1),
    }


def _ventana(plantilla):
    """De qué hora a qué hora se dibuja la rejilla, redondeado a la hora entera.

    Nunca menos que la jornada laboral, y más si hace falta. El cliente pidió
    bloques fuera del horario laboral (US-06 AC6) y con una ventana fija uno de
    las 20:00 no se vería en ninguna parte.
    """
    piso, techo = JORNADA_MINIMA
    horas = [(minutos(b.inicio), minutos(b.termino)) for bs in plantilla.values() for b in bs]
    if not horas:
        return JORNADA_MINIMA
    return (
        min(piso, min(i for i, _ in horas) // 60 * 60),
        max(techo, -(-max(f for _, f in horas) // 60) * 60),
    )


def _ubicar(plantilla, desde, largo):
    """Dónde empieza cada bloque y cuánto ocupa, en porcentaje de la jornada.

    Se formatean acá porque un float en la plantilla saldría con coma decimal
    (el proyecto está en es-CL) y eso no es CSS válido.
    """
    for bloques in plantilla.values():
        for bloque in bloques:
            bloque.posicion = f"{(minutos(bloque.inicio) - desde) / largo * 100:.4f}"
            bloque.largo = f"{bloque.dura / largo * 100:.4f}"


def _reloj(desde, hasta, largo):
    return [
        {"etiqueta": f"{hora:02d}:00", "posicion": f"{(hora * 60 - desde) / largo * 100:.4f}"}
        for hora in range(desde // 60, hasta // 60 + 1)
    ]


def _duracion(total):
    horas, resto = divmod(total, 60)
    return f"{horas} h" if not resto else f"{horas} h {resto:02d}"


def _resumen(bloques):
    if not bloques:
        return "Sin bloques"
    jornada = _duracion(sum(b.dura for b in bloques))
    if len(bloques) == 1:
        return f"1 bloque, {jornada}"
    return f"{len(bloques)} bloques, {jornada}"


def _cabeceras(plantilla):
    """Cuánta jornada tiene cada día de la semana, y cuál se sale del molde.

    Se dice una vez por columna porque la plantilla se repite todas las semanas.
    """
    forma = {d: tuple((b.inicio, b.termino) for b in plantilla[d]) for d in Dia.values}
    comun = Counter(forma.values()).most_common(1)[0][0]
    return [
        {
            "nombre": Dia(d).label.capitalize(),
            "resumen": _resumen(plantilla[d]),
            "distinto": forma[d] != comun,
        }
        for d in Dia.values
    ]


def _hhmm(total):
    return f"{total // 60:02d}:{total % 60:02d}"


def _proximo(bloques):
    """Dónde caería un bloque nuevo, pegado al último del día y de 90 minutos.
    Es la sugerencia que trae el formulario, no una regla."""
    inicio = bloques[-1].termino if bloques else time(8, 10)
    return {"inicio": f"{inicio:%H:%M}", "termino": _hhmm(min(minutos(inicio) + 90, 23 * 60 + 55))}


def _dia(fecha, plantilla, foco=None, bloqueos=None, hoy=None):
    bloques = plantilla[fecha.weekday()]
    del_dia = (bloqueos or {}).get(fecha, [])
    return {
        "fecha": fecha,
        "numero": fecha.weekday(),
        "fuera": foco is not None and fecha.month != foco.month,
        "bloques": bloques,
        "proximo": _proximo(bloques),
        # US-17. La mensual los dibuja en la celda; la semanal raya los bloques
        # que dejan fuera, y para eso le basta con los `pk`.
        "bloqueos": del_dia,
        "bloqueados": {b.pk for b in bloques if any(x.cubre(fecha, b.inicio) for x in del_dia)},
        "entero": any(b.bloque_id is None for b in del_dia),
        "pasado": hoy is not None and fecha < hoy,
    }


def _estado_bloqueo(formulario):
    """Con qué arranca el editor de bloqueos.

    Sale de lo que mandó el navegador, sin limpiar, y va al x-data de Alpine.
    Por eso cada valor se revisa antes: una fecha o un modo inventados romperían
    el JavaScript de la página.
    """
    if formulario is None or not formulario.is_bound:
        return {"abierto": False, "fecha": "", "hasta": "", "modo": "dia",
                "bloque": None, "motivo": "", "detalle": ""}

    def dato(campo):
        return formulario.data.get(formulario.add_prefix(campo), "")

    fecha, hasta = _fecha(dato("desde"), None), _fecha(dato("hasta"), None)
    try:
        bloque = int(dato("bloque"))
    except ValueError:
        bloque = None
    return {
        "abierto": True,
        "fecha": fecha.isoformat() if fecha else "",
        "hasta": hasta.isoformat() if hasta else "",
        "modo": dato("modo") if dato("modo") in dict(MODOS) else "dia",
        "bloque": bloque,
        "motivo": dato("motivo") if dato("motivo") in Motivo.values else "",
        # Este no va al x-data: la plantilla lo escribe en el value del campo.
        "detalle": dato("detalle"),
    }


def _proximas(hoy, semana=()):
    """Las próximas fechas de cada día de la semana, para bloquear un bloque desde
    la vista semanal. Un día ya bloqueado entero va marcado, porque ahí no queda
    nada que bloquear. La fecha de la semana que se está mirando viene elegida."""
    hasta = hoy + timedelta(weeks=SEMANAS_PARA_BLOQUEAR)
    bloqueos = bloqueos_por_fecha(hoy, hasta)
    por_dia = {d: [] for d in Dia.values}
    fecha = hoy
    while fecha < hasta:
        if fecha.weekday() in por_dia:
            por_dia[fecha.weekday()].append({
                "fecha": fecha,
                "entero": any(b.bloque_id is None for b in bloqueos.get(fecha, [])),
                "elegida": fecha in semana,
            })
        fecha += timedelta(days=1)
    return [{"numero": d, "fechas": fechas} for d, fechas in por_dia.items()]


def _registro():
    """US-17 AC6: los últimos bloqueos y levantamientos, cada uno con quién, cuándo
    y por qué. Un bloqueo levantado aparece dos veces, una por cada acción."""
    recientes = Bloqueo.objects.select_related(
        "bloque", "bloqueado_por", "levantado_por"
    ).order_by(Coalesce("levantado_en", "bloqueado_en").desc())[:ULTIMOS]
    acciones = []
    for bloqueo in recientes:
        acciones.append({"cuando": bloqueo.bloqueado_en, "accion": "Bloqueo", "bloqueo": bloqueo,
                         "motivo": bloqueo.razon, "quien": bloqueo.bloqueado_por})
        if bloqueo.levantado_en:
            acciones.append({"cuando": bloqueo.levantado_en, "accion": "Levantamiento",
                             "bloqueo": bloqueo, "motivo": bloqueo.motivo_levantamiento,
                             "quien": bloqueo.levantado_por})
    return sorted(acciones, key=lambda a: a["cuando"], reverse=True)[:ULTIMOS]


# Lo que la plantilla mete en el x-data de Alpine. Sin nada elegido va la palabra
# `null`, para que el objeto de JavaScript se escriba igual en los dos casos.
SIN_ELEGIR = {"pk": "null", "dian": "null", "dia": "", "ini": "", "fin": ""}


def _elegido(bloque):
    """El bloque abierto en el editor. Sin `pk` es un alta que no pasó la
    validación y vuelve con lo que el administrador escribió."""
    if bloque is None:
        return SIN_ELEGIR
    return {
        "pk": bloque.pk or "null",
        "dian": bloque.dia,
        "dia": bloque.get_dia_display(),
        # Un alta con la hora en blanco llega sin `inicio`, así que el campo
        # va vacío.
        "ini": f"{bloque.inicio:%H:%M}" if bloque.inicio else "",
        "fin": f"{bloque.termino:%H:%M}" if bloque.termino else "",
    }


def _contexto(datos, error=None, elegido=None, quitado=None, choca=None,
              bloqueo=None, afectadas=(), levantando=None, error_levantar=None):
    """Todo lo que necesita el calendario. Lo comparten la vista que lo muestra
    y las que guardan un bloque o un bloqueo, porque todas dibujan la misma
    rejilla."""
    # US-02 AC7: la vista por defecto es la mensual, pedida por el cliente.
    vista = datos.get("vista")
    if vista not in ("mes", "semana"):
        vista = "mes"
    hoy = timezone.localdate()
    # La rejilla es de lunes a viernes: un sábado o domingo, "Hoy" lleva a la
    # semana que viene y no a la que ya terminó.
    por_defecto = hoy
    if vista == "semana" and hoy.weekday() >= 5:
        por_defecto = hoy + timedelta(days=7 - hoy.weekday())
    foco = _fecha(datos.get("desde"), por_defecto)

    plantilla = plantilla_semanal()
    desde, hasta = _ventana(plantilla)
    largo = hasta - desde
    _ubicar(plantilla, desde, largo)
    fechas = _semana(foco)
    mes = _mes(foco)
    if vista == "mes":
        bloqueos = bloqueos_por_fecha(mes[0][0], mes[-1][-1])
    else:
        bloqueos = bloqueos_por_fecha(fechas[0], fechas[-1])

    return {
        "pestana": "bloques",
        "vista": vista,
        "foco": foco,
        "hoy": hoy,
        "titulo": _titulo(vista, foco),
        "reloj": _reloj(desde, hasta, largo),
        # Cuántas horas mide la rejilla; de acá sale el alto de la columna.
        "altura": largo // 60,
        # En minutos, para que el navegador traduzca un clic a una hora sin
        # parsear las etiquetas del reloj.
        "desde_min": desde,
        "largo_min": largo,
        "cabeceras": _cabeceras(plantilla),
        "dias": [_dia(fecha, plantilla, None, bloqueos, hoy) for fecha in fechas],
        "mini": _mini(foco, hoy) if vista == "semana" else None,
        "semanas": [[_dia(f, plantilla, foco, bloqueos, hoy) for f in s] for s in mes],
        "anterior": _correr(foco, vista, -1),
        "siguiente": _correr(foco, vista, +1),
        "error": error,
        "elegido": _elegido(elegido),
        # Quitar un bloque no se confirma antes, se deshace después.
        "quitado": quitado,
        # El bloque contra el que se chocó, para señalarlo en la rejilla.
        "choca": choca.pk if choca is not None else None,
        # US-17, vista mensual. Los bloqueos del mes sin repetir, para el panel
        # de cada uno; uno de varios días aparece en varias celdas.
        "bloqueos_mes": list({b.pk: b for bs in bloqueos.values() for b in bs}.values()) if vista == "mes" else [],
        "jornada": [{"numero": d, "bloques": plantilla[d]} for d in Dia.values],
        "motivos": Motivo.choices,
        "modos": MODOS,
        "bq": _estado_bloqueo(bloqueo),
        "bq_errores": _mensaje(bloqueo) if bloqueo is not None and bloqueo.is_bound else None,
        "afectadas": afectadas,
        "confirmadas": ",".join(r.codigo for r in afectadas),
        "levantando": levantando,
        # Lo que no dejó levantar un bloqueo: va dentro de su pop-up.
        "error_levantar": error_levantar,
        "registro": _registro() if vista == "mes" else [],
        "proximas": _proximas(hoy, fechas) if vista == "semana" else [],
    }


@staff_member_required(login_url="login_gestion")
def bloques(request):
    contexto = _contexto(request.GET)
    # htmx pide solo la rejilla. El navegador sin htmx pide la página entera y
    # recibe lo mismo dentro de ella, igual que htmx al volver con Atrás sin la
    # página en su caché (HX-History-Restore-Request).
    if request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request"):
        return render(request, "agenda/_calendario.html", contexto)
    return render(request, "agenda/bloques.html", contexto)


def _mensaje(formulario):
    """Los errores en una línea, que es lo que cabe en el pop-up."""
    return " ".join(m for grupo in formulario.errors.values() for m in grupo)


def _responder(request, **extra):
    """htmx recibe la rejilla ya redibujada. El navegador sin htmx recibe una
    redirección, para que recargar no reenvíe el formulario, y el error va como
    aviso porque no hay pop-up que lo muestre."""
    if request.headers.get("HX-Request"):
        return render(request, "agenda/_calendario.html", _contexto(request.POST, **extra))
    if extra.get("error"):
        messages.error(request, extra["error"])
    destino = f"{reverse('panel_bloques')}?vista=semana&desde={request.POST.get('desde', '')}"
    return redirect(destino)


@staff_member_required(login_url="login_gestion")
@require_POST
def editar_bloque(request):
    """Agrega, cambia, quita o repone un bloque de la plantilla.

    Las cuatro acciones comparten vista porque devuelven la misma rejilla. El
    cambio vale para ese día de la semana, todas las semanas.
    """
    accion = request.POST.get("accion", "guardar")

    if accion in ("quitar", "reponer"):
        bloque = get_object_or_404(Bloque, pk=request.POST.get("bloque"))
        if accion == "quitar":
            bloque.activo = False
            bloque.save(update_fields=["activo"])
            # Con htmx, el aviso con «Reponerlo» lo dibuja la rejilla, porque lleva
            # un formulario. Sin htmx queda solo el mensaje.
            if not request.headers.get("HX-Request"):
                messages.success(request, f"Quitaste el bloque de los {_nombre(bloque)}.")
            return _responder(request, quitado=bloque)
        # Reponer puede chocar, porque mientras estuvo fuera alguien pudo
        # ocupar la hora.
        bloque.activo = True
        try:
            bloque.full_clean(exclude=["dia"])
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return _responder(request, quitado=bloque, choca=bloque.cruce())
        bloque.save(update_fields=["activo"])
        messages.success(request, f"Repusiste el bloque de los {_nombre(bloque)}.")
        return _responder(request)

    # Guardar y agregar usan el mismo formulario; lo que cambia es la instancia.
    pk = request.POST.get("bloque")
    if pk:
        bloque = get_object_or_404(Bloque, pk=pk)
    else:
        dia = request.POST.get("dia")
        if dia not in {str(d) for d in Dia.values}:
            return HttpResponseBadRequest("Día fuera de la semana laboral")
        bloque = Bloque(dia=int(dia))

    formulario = BloqueForm(request.POST, instance=bloque)
    if formulario.is_valid():
        formulario.save()
        messages.success(request, f"Guardaste el bloque de los {_nombre(bloque)}. Vale para todas las semanas.")
        return _responder(request)
    # `cruce()` de nuevo solo en el camino del error, para señalar el otro.
    return _responder(request, error=_mensaje(formulario), elegido=bloque, choca=bloque.cruce())


def _responder_mes(request, listo=False, **extra):
    """Como `_responder`, pero para la vista mensual, que es la que tiene fechas.

    Sin htmx una advertencia o un error no pueden ir en una redirección, así
    que se dibuja la página entera. Solo lo que ya quedó hecho redirige, para
    que recargar no bloquee dos veces.
    """
    datos = request.POST.copy()
    datos["vista"] = "mes"
    # Desde la vista semanal no llega el mes que se estaba mirando, así que se
    # muestra el de la fecha bloqueada.
    datos.setdefault("desde", datos.get("bq-desde", ""))
    contexto = _contexto(datos, **extra)
    direccion = f"{reverse('panel_bloques')}?vista=mes&desde={contexto['foco']:%Y-%m-%d}"
    if request.headers.get("HX-Request"):
        respuesta = render(request, "agenda/_calendario.html", contexto)
        # Que la barra de direcciones diga lo que se ve, y recargar no vuelva a
        # la vista semanal.
        respuesta["HX-Push-Url"] = direccion
        return respuesta
    if listo:
        return redirect(direccion)
    return render(request, "agenda/bloques.html", contexto)


def _nombre(bloque):
    return f"{bloque.get_dia_display()}, {bloque.inicio:%H:%M}–{bloque.termino:%H:%M}"


def _personas(reservas):
    cuantas = len({r.correo for r in reservas})
    return "1 persona" if cuantas == 1 else f"{cuantas} personas"


@staff_member_required(login_url="login_gestion")
@require_POST
def editar_bloqueo(request):
    """Bloquea la sala en unas fechas, o levanta un bloqueo (US-17).

    Si el bloqueo le quita la sala a reservas aprobadas, la primera vez no se
    guarda: vuelve con la lista para que el administrador la vea (AC4). Al
    confirmar, el navegador devuelve los códigos que se le mostraron, y si ya no
    son los mismos se le vuelve a mostrar la lista antes de avisar a nadie.
    """
    if request.POST.get("accion") == "levantar":
        bloqueo = get_object_or_404(Bloqueo, pk=request.POST.get("bloqueo"))
        formulario = LevantarForm(request.POST)
        if not formulario.is_valid():
            return _responder_mes(request, levantando=bloqueo.pk, error_levantar=_mensaje(formulario))
        try:
            services.levantar(bloqueo, request.user, formulario.cleaned_data["motivo"])
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return _responder_mes(request)
        messages.success(
            request,
            f"Levantaste el bloqueo por {bloqueo.get_motivo_display()}. La sala vuelve a "
            f"estar disponible {bloqueo.periodo}, {bloqueo.alcance}.",
        )
        return _responder_mes(request, listo=True)

    formulario = BloqueoForm(request.POST)
    if not formulario.is_valid():
        return _responder_mes(request, bloqueo=formulario)

    bloqueo = formulario.save(commit=False)
    afectadas = services.afectadas(bloqueo)
    vistas = {c for c in request.POST.get("confirmadas", "").split(",") if c}
    if afectadas and {r.codigo for r in afectadas} != vistas:
        return _responder_mes(request, bloqueo=formulario, afectadas=afectadas)

    services.bloquear(bloqueo, request.user, afectadas)
    hecho = f"Bloqueaste la sala {bloqueo.periodo}, {bloqueo.alcance} ({bloqueo.razon})."
    if afectadas:
        hecho += f" Se le avisó por correo a {_personas(afectadas)}."
    messages.success(request, hecho)
    return _responder_mes(request, listo=True)
