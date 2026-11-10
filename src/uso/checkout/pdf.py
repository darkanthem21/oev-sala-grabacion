"""PDF del formulario respondido, generado en memoria con tipografías de marca."""

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from django.contrib.staticfiles import finders
from django.utils import timezone
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .services import casos_falta_integridad, resumen_respuestas


@lru_cache(maxsize=1)
def _marca():
    fuentes = Path(__file__).with_name("fonts")
    pdfmetrics.registerFont(TTFont("CheckoutRoboto", str(fuentes / "Roboto-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("CheckoutMontserrat", str(fuentes / "Montserrat-Bold.ttf")))
    pdfmetrics.registerFontFamily("CheckoutRoboto", normal="CheckoutRoboto", bold="CheckoutMontserrat")
    css = Path(finders.find("css/marca.css")).read_text(encoding="utf-8")
    valores = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6}|var\(--[\w-]+\))", css))
    # Algunas variables son alias de otra (--acento: var(--marca)).
    def hexadecimal(nombre):
        valor = valores[nombre]
        return hexadecimal(valor[6:-1]) if valor.startswith("var(") else valor
    return {nombre: colors.HexColor(hexadecimal(nombre)) for nombre in valores}


def generar_pdf(registro):
    paleta = _marca()
    salida = BytesIO()
    doc = SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=38 * mm, bottomMargin=20 * mm,
        title=f"Check-out {registro.ticket.ticket}", author="Oficina de Educación Virtual · FCI UACh",
    )
    cuerpo = ParagraphStyle("Texto", fontName="CheckoutRoboto", fontSize=9, leading=13, textColor=paleta["tinta"], spaceAfter=6, alignment=TA_LEFT)
    titulo = ParagraphStyle("Titulo", parent=cuerpo, fontName="CheckoutMontserrat", fontSize=16, leading=21, spaceAfter=12, keepWithNext=True)
    seccion = ParagraphStyle("Seccion", parent=cuerpo, fontName="CheckoutMontserrat", fontSize=11, leading=15, spaceBefore=12, keepWithNext=True)
    etiqueta = ParagraphStyle("Etiqueta", parent=cuerpo, fontName="CheckoutMontserrat", fontSize=9, leading=13)
    contenido = []

    def parrafo(texto, estilo=cuerpo):
        return Paragraph(escape(str(texto or "")).replace("\n", "<br/>"), estilo)

    def texto(valor, estilo=cuerpo):
        contenido.append(parrafo(valor, estilo))

    def fotografia(campo, leyenda):
        if not campo:
            texto(f"{leyenda}: no registrada.")
            return
        try:
            with campo.open("rb") as archivo, PILImage.open(archivo) as original:
                if original.width * original.height > 30_000_000:
                    raise ValueError("Imagen demasiado grande para el documento")
                imagen = original.convert("RGB")
                imagen.thumbnail((1600, 1600))
                datos = BytesIO()
                imagen.save(datos, format="JPEG", quality=85)
                ancho, alto = imagen.size
            datos.seek(0)
            escala = min(155 * mm / ancho, 75 * mm / alto)
            texto(leyenda, etiqueta)
            contenido.append(Image(datos, width=ancho * escala, height=alto * escala, hAlign="LEFT"))
            contenido.append(Spacer(1, 4 * mm))
        except (OSError, ValueError, PILImage.DecompressionBombError):
            texto(f"{leyenda}: imagen no disponible para incorporar al PDF.")

    solicitado = registro.ticket.solicitud
    tiene_reporte = getattr(registro, "tiene_reporte", None)
    if tiene_reporte is None:
        tiene_reporte = casos_falta_integridad(registro).exists()
    texto(f"Formulario de check-out · {registro.ticket.ticket}", titulo)
    datos = [
        ("Solicitante", solicitado.solicitante.get_full_name() or solicitado.solicitante.email),
        ("Área", solicitado.area.nombre),
        ("Fecha de reserva", registro.ticket.fecha.strftime("%d/%m/%Y")),
        ("Bloque", f"{registro.ticket.inicio:%H:%M}–{registro.ticket.termino:%H:%M}"),
        ("Fecha de registro", timezone.localtime(registro.registrado_en).strftime("%d/%m/%Y %H:%M:%S")),
        ("Registrado por", str(registro.registrado_por or "Usuario eliminado")),
        ("Asistencia", "Asistió" if registro.asistio else "Inasistencia"),
        ("Reporte de integridad", "Sí · Con incumplimientos" if tiene_reporte else "No"),
    ]
    tabla = Table([[parrafo(nombre, etiqueta), parrafo(valor)] for nombre, valor in datos], colWidths=[49 * mm, doc.width - 49 * mm], hAlign="LEFT")
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), .4, paleta["borde"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    contenido.append(tabla)
    if registro.editado_en:
        texto(f"Editado por {registro.editado_por or 'Usuario eliminado'} el {timezone.localtime(registro.editado_en):%d/%m/%Y %H:%M:%S}.", seccion)
    if not registro.asistio:
        texto("Inasistencia registrada. No se realizó el formulario de revisión de integridad de la sala.", seccion)
    else:
        for bloque in resumen_respuestas(registro):
            texto(bloque["titulo"], seccion)
            for pregunta in bloque["preguntas"]:
                texto(pregunta["texto"], etiqueta)
                texto("Respuesta: " + ("Sí" if pregunta["cumple"] else "No") if pregunta["respondida"] else "Sin respuesta registrada.")
                if pregunta["respondida"] and not pregunta["cumple"]:
                    texto("Observación del incumplimiento: " + pregunta["observacion"])
                    foto = pregunta["foto"]
                    fotografia(foto.archivo if foto else None, "Fotografía de integridad")
        texto("Fundamento y evidencia final", seccion)
        texto("Hora efectiva de salida: " + (registro.hora_salida.strftime("%H:%M") if registro.hora_salida else "No registrada"))
        texto("Observaciones finales: " + registro.observaciones)
        fotografia(registro.foto_final, "Fotografía final de la sala")
        if registro.recomendaciones:
            texto("Recomendaciones finales: " + registro.recomendaciones)

    logo = finders.find("img/Facultad-color-negro.png")
    generado = timezone.localtime().strftime("%d/%m/%Y %H:%M")

    def encabezado(canvas, documento):
        canvas.saveState()
        ancho, alto = A4
        if logo:
            canvas.drawImage(logo, 18 * mm, alto - 27 * mm, width=40 * mm, height=16 * mm, preserveAspectRatio=True, mask="auto")
        canvas.setFillColor(paleta["tinta"])
        canvas.setFont("CheckoutMontserrat", 10)
        canvas.drawString(64 * mm, alto - 18 * mm, "Oficina de Educación Virtual")
        canvas.setFont("CheckoutRoboto", 8)
        canvas.drawString(64 * mm, alto - 23 * mm, "Facultad de Ciencias de la Ingeniería · UACh")
        canvas.setStrokeColor(paleta["acento"])
        canvas.line(18 * mm, alto - 31 * mm, ancho - 18 * mm, alto - 31 * mm)
        canvas.setFillColor(paleta["tinta-suave"])
        canvas.setFont("CheckoutRoboto", 7)
        canvas.drawString(18 * mm, 11 * mm, f"Generado el {generado} · {registro.ticket.ticket}")
        canvas.drawRightString(ancho - 18 * mm, 11 * mm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(contenido, onFirstPage=encabezado, onLaterPages=encabezado)
    salida.seek(0)
    return salida
