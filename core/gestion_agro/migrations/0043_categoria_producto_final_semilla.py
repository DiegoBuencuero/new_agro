from django.db import migrations


def add_categoria_pfs(apps, schema_editor):
    CategoriaProducto = apps.get_model("gestion_agro", "CategoriaProducto")
    CategoriaProducto.objects.get_or_create(
        codigo="PFS",
        defaults={"nombre": "Producto Final - Semilla", "es_semilla": True},
    )


def remove_categoria_pfs(apps, schema_editor):
    CategoriaProducto = apps.get_model("gestion_agro", "CategoriaProducto")
    CategoriaProducto.objects.filter(codigo="PFS").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_agro", "0042_alter_campo_descripcion"),
    ]

    operations = [
        migrations.RunPython(
            add_categoria_pfs,
            remove_categoria_pfs,
        ),
    ]
