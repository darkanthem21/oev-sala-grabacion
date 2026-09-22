from django.db import migrations

# Escritos aca y no importados de `Rol`: una migracion tiene que seguir diciendo
# lo mismo dentro de diez commits, aunque el codigo se renombre.
ROLES = ["Administrador", "Validador", "Personal de apoyo", "Solicitante"]


def crear(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nombre in ROLES:
        Group.objects.get_or_create(name=nombre)


def borrar(apps, schema_editor):
    # Solo los grupos vacios: si alguien ya tiene el rol, quitarselo al revertir
    # una migracion seria una sorpresa desagradable.
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLES, user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("personas", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(crear, borrar)]
