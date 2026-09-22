from django.db import migrations

# Escritos acá en vez de importados de `Rol`, porque una migración tiene que
# seguir diciendo lo mismo aunque el código se renombre.
ROLES = ["Administrador", "Validador", "Personal de apoyo", "Solicitante"]


def crear(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nombre in ROLES:
        Group.objects.get_or_create(name=nombre)


def borrar(apps, schema_editor):
    # Solo los grupos vacíos. Quitarle el rol a alguien por revertir una
    # migración sería una sorpresa fea.
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLES, user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("personas", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(crear, borrar)]
