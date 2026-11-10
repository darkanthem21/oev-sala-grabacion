from django.db import migrations


def normalizar(apps, schema_editor):
    Checkout = apps.get_model("uso", "Checkout")
    Respuesta = apps.get_model("uso", "RespuestaCheckout")
    Foto = apps.get_model("uso", "FotoIntegridad")
    base = schema_editor.connection.alias
    for registro in Checkout.objects.using(base).iterator():
        for seccion in registro.formulario:
            for pregunta in seccion["preguntas"]:
                datos = registro.respuestas.get(pregunta["id"])
                if datos is None:
                    continue
                cumple = datos["cumple"]
                respuesta, _ = Respuesta.objects.using(base).get_or_create(
                    checkout_id=registro.pk, pregunta=pregunta["id"],
                    defaults={
                        "texto": pregunta["texto"], "seccion": seccion["titulo"], "cumple": cumple,
                        "observacion": datos.get("observacion", "") if not cumple else "",
                        "recomendacion": datos.get("recomendacion", "") if not cumple else "",
                    },
                )
                foto = Foto.objects.using(base).filter(checkout_id=registro.pk, pregunta=pregunta["id"]).order_by("pk").first()
                if foto:
                    Foto.objects.using(base).filter(pk=foto.pk).update(respuesta_id=respuesta.pk)


class Migration(migrations.Migration):
    dependencies = [("uso", "0002_respuestas_y_evidencia_final")]
    operations = [migrations.RunPython(normalizar, migrations.RunPython.noop)]
