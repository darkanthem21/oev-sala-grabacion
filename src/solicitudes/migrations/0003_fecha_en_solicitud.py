"""La fecha pasa de cada SolicitudBloque a la Solicitud.

Una solicitud es de un solo día y el asistente siempre guardó la misma fecha
en todos sus bloques, pero el modelo no lo exigía. Con la fecha en la
solicitud, el esquema lo garantiza.

El orden de las operaciones permite revertirla: la fecha de los bloques se
vuelve opcional antes de copiar, así que al deshacer se recupera, se rellena
desde la solicitud y recién entonces vuelve a ser obligatoria.
"""

from django.db import migrations, models
from django.db.models import Min
from django.utils import timezone


def copiar_fecha_a_la_solicitud(apps, schema_editor):
    Solicitud = apps.get_model("solicitudes", "Solicitud")
    # Si una solicitud tuviera bloques de días distintos, queda el primero:
    # el asistente nunca los creó, pero el admin lo permitía.
    for solicitud in Solicitud.objects.annotate(primera=Min("solicitudes_bloques__fecha")):
        # Sin bloques no hay fecha pedida: queda el día en que se creó.
        solicitud.fecha = solicitud.primera or timezone.localtime(solicitud.creado_en).date()
        solicitud.save(update_fields=["fecha"])


def devolver_fecha_a_los_bloques(apps, schema_editor):
    SolicitudBloque = apps.get_model("solicitudes", "SolicitudBloque")
    for sb in SolicitudBloque.objects.select_related("solicitud"):
        sb.fecha = sb.solicitud.fecha
        sb.save(update_fields=["fecha"])


class Migration(migrations.Migration):

    dependencies = [
        ("solicitudes", "0002_estado_validacion_retirada"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitud",
            name="fecha",
            field=models.DateField(null=True, verbose_name="fecha de la reserva"),
        ),
        migrations.AlterField(
            model_name="solicitudbloque",
            name="fecha",
            field=models.DateField(null=True, verbose_name="fecha de la reserva"),
        ),
        migrations.RunPython(copiar_fecha_a_la_solicitud, devolver_fecha_a_los_bloques),
        migrations.AlterField(
            model_name="solicitud",
            name="fecha",
            field=models.DateField(verbose_name="fecha de la reserva"),
        ),
        migrations.RemoveConstraint(
            model_name="solicitudbloque",
            name="solicitud_bloque_fecha_unica",
        ),
        migrations.RemoveField(
            model_name="solicitudbloque",
            name="fecha",
        ),
        migrations.AddConstraint(
            model_name="solicitudbloque",
            constraint=models.UniqueConstraint(fields=("solicitud", "bloque"), name="solicitud_bloque_unico"),
        ),
    ]
