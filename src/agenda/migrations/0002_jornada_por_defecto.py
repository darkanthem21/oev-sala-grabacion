from datetime import time

from django.db import migrations

# Decisión 1 del diseño: seis bloques de 90 min de lunes a viernes, con la
# colación entre las 12:40 y las 14:10, que es el hueco y no una fila. Es el
# "valor por defecto cargado" que pide US-04 AC2, y desde acá se edita.
#
# Pendiente con el cliente: de la Maza fijó bloques de 1,5 h (05/08) y José Tomás
# un mínimo de reserva de 2 h (06/08). La reunión del 21/08 no dejó minuta, así
# que esto es la propuesta del equipo y no una respuesta.
HORARIO = [
    (time(8, 10), time(9, 40)),
    (time(9, 40), time(11, 10)),
    (time(11, 10), time(12, 40)),
    (time(14, 10), time(15, 40)),
    (time(15, 40), time(17, 10)),
    (time(17, 10), time(18, 40)),
]


def cargar(apps, schema_editor):
    Bloque = apps.get_model("agenda", "Bloque")
    Bloque.objects.bulk_create(
        [
            Bloque(dia=dia, inicio=inicio, termino=termino)
            for dia in range(5)
            for inicio, termino in HORARIO
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [("agenda", "0001_initial")]

    # Sin vuelta atrás, porque revertir borraría la jornada que el administrador
    # haya editado desde el panel.
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
