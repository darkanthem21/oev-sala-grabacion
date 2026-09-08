import calendar
from collections import Counter
from datetime import date, time, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from .forms import BloqueForm
from .models import Bloque, Dia, minutos, plantilla_semanal

# Piso de la rejilla. Sin el, la escala cambiaria con los datos —un dia con un
# solo bloque lo mostraria ocupando toda la jornada— y dos dias dejarian de ser
# comparables, que es justo para lo que sirve la vista mensual.
JORNADA_MINIMA = (8 * 60, 19 * 60)


def _fecha(texto, por_defecto):
    """La fecha llega por la barra de direcciones: cualquiera puede escribirla."""
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


def _titulo(vista, foco, fechas):
    """El periodo que se esta mirando, escrito como lo diria una persona."""
    if vista == "mes":
        return date_format(foco, "F Y").capitalize()
    inicio, fin = fechas[0], fechas[-1]
    if inicio.month == fin.month:
        return f"{inicio.day}–{fin.day} de {date_format(fin, 'F Y')}"
    return f"{date_format(inicio, 'j F')} – {date_format(fin, 'j F Y')}"


def _ventana(plantilla):
    """De que hora a que hora se dibuja la rejilla, redondeado a la hora entera.

    Nunca menos que la jornada laboral y mas si hace falta: el cliente pidio
    bloques fuera del horario laboral (US-06 AC6, 06/08 03:48), y con una ventana
    fija uno de las 20:00 no se veria en ninguna parte.
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
    """Donde empieza cada bloque y cuanto ocupa, en porcentaje de la jornada.

    Sin eje: la semana los usa como `top`/`height` y el mes como `left`/`width`, y
    por ser porcentajes la misma cifra sirve en las dos escalas. Se formatean aca
    porque un float en la plantilla saldria con coma decimal —el proyecto esta en
    es-CL— y eso no es CSS valido.
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
    """Cuanta jornada tiene cada dia de la semana, y cual se sale del molde.

    Se dice una vez por columna y no treinta veces en las celdas: la plantilla se
    repite todas las semanas.
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
    """Donde caeria un bloque nuevo: pegado al ultimo del dia y de 90 minutos. Es
    la sugerencia que trae el formulario, no una regla."""
    inicio = bloques[-1].termino if bloques else time(8, 10)
    return {"inicio": f"{inicio:%H:%M}", "termino": _hhmm(min(minutos(inicio) + 90, 23 * 60 + 55))}


def _dia(fecha, plantilla, foco=None):
    bloques = plantilla[fecha.weekday()]
    return {
        "fecha": fecha,
        "numero": fecha.weekday(),
        "fuera": foco is not None and fecha.month != foco.month,
        "bloques": bloques,
        "proximo": _proximo(bloques),
    }


# Lo que la plantilla mete en el x-data de Alpine. Cuando no hay nada elegido va
# la palabra `null` para que el objeto de JavaScript quede escrito igual en los
# dos casos y la plantilla no lleve condicionales.
SIN_ELEGIR = {"pk": "null", "dian": "null", "dia": "", "ini": "", "fin": ""}


def _elegido(bloque):
    """El bloque abierto en el editor. Sin `pk` es un alta que no paso la
    validacion y vuelve con lo que el administrador escribio."""
    if bloque is None:
        return SIN_ELEGIR
    return {
        "pk": bloque.pk or "null",
        "dian": bloque.dia,
        "dia": bloque.get_dia_display(),
        # Un alta con la hora en blanco llega sin `inicio`: campo vacio, no un None
        # formateado.
        "ini": f"{bloque.inicio:%H:%M}" if bloque.inicio else "",
        "fin": f"{bloque.termino:%H:%M}" if bloque.termino else "",
    }


def _contexto(datos, error=None, elegido=None, quitado=None, choca=None):
    """Todo lo que necesita el calendario. Lo comparten la vista que lo muestra y
    la que guarda un bloque, porque las dos terminan dibujando la misma rejilla."""
    # US-02 AC7: la vista por defecto es la mensual, pedida por el cliente.
    vista = datos.get("vista")
    if vista not in ("mes", "semana"):
        vista = "mes"
    hoy = timezone.localdate()
    foco = _fecha(datos.get("desde"), hoy)

    plantilla = plantilla_semanal()
    desde, hasta = _ventana(plantilla)
    largo = hasta - desde
    _ubicar(plantilla, desde, largo)
    fechas = _semana(foco)

    return {
        "pestana": "bloques",
        "vista": vista,
        "foco": foco,
        "hoy": hoy,
        "titulo": _titulo(vista, foco, fechas),
        "reloj": _reloj(desde, hasta, largo),
        # Cuantas horas mide la rejilla: el alto de la columna sale de aca.
        "altura": largo // 60,
        "cabeceras": _cabeceras(plantilla),
        "dias": [_dia(fecha, plantilla) for fecha in fechas],
        "semanas": [[_dia(f, plantilla, foco) for f in s] for s in _mes(foco)],
        "anterior": _correr(foco, vista, -1),
        "siguiente": _correr(foco, vista, +1),
        "error": error,
        "elegido": _elegido(elegido),
        # Un bloque quitado no se confirma antes: se deshace despues.
        "quitado": quitado,
        # El bloque contra el que se choco, para senalarlo en la rejilla.
        "choca": choca.pk if choca is not None else None,
    }


@staff_member_required(login_url="login_gestion")
def bloques(request):
    contexto = _contexto(request.GET)
    # htmx pide solo la rejilla; el navegador sin htmx pide la pagina entera y
    # recibe lo mismo dentro de ella.
    if request.headers.get("HX-Request"):
        return render(request, "agenda/_calendario.html", contexto)
    return render(request, "agenda/bloques.html", contexto)


def _mensaje(formulario):
    """Los errores en una linea: el aviso vive en la barra, no en un panel."""
    return " ".join(m for grupo in formulario.errors.values() for m in grupo)


def _responder(request, **extra):
    """htmx recibe la rejilla ya redibujada; el navegador sin htmx, una redireccion
    para que recargar no reenvie el formulario."""
    if request.headers.get("HX-Request"):
        return render(request, "agenda/_calendario.html", _contexto(request.POST, **extra))
    destino = f"{reverse('panel_bloques')}?vista=semana&desde={request.POST.get('desde', '')}"
    return redirect(destino)


@staff_member_required(login_url="login_gestion")
@require_POST
def editar_bloque(request):
    """Agrega, cambia, quita o repone un bloque de la plantilla.

    Las cuatro acciones comparten vista porque las cuatro devuelven la misma
    rejilla. El cambio vale para ese dia de la semana, todas las semanas.
    """
    accion = request.POST.get("accion", "guardar")

    if accion in ("quitar", "reponer"):
        bloque = get_object_or_404(Bloque, pk=request.POST.get("bloque"))
        if accion == "quitar":
            bloque.activo = False
            bloque.save(update_fields=["activo"])
            return _responder(request, quitado=bloque)
        # Reponer puede chocar: mientras estuvo fuera, alguien pudo ocupar la hora.
        bloque.activo = True
        try:
            bloque.full_clean(exclude=["dia"])
        except ValidationError as error:
            return _responder(
                request, error=" ".join(error.messages), quitado=bloque, choca=bloque.cruce()
            )
        bloque.save(update_fields=["activo"])
        return _responder(request, elegido=bloque)

    # Guardar y agregar son el mismo formulario: cambia la instancia, no la regla.
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
        return _responder(request, elegido=bloque)
    # `cruce()` de nuevo solo en el camino del error, para poder senalar el otro.
    return _responder(request, error=_mensaje(formulario), elegido=bloque, choca=bloque.cruce())
