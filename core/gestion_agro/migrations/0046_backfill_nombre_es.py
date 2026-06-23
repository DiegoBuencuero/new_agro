from django.db import migrations


def backfill_nombre_es(apps, schema_editor):
    TipoActividad = apps.get_model("gestion_agro", "TipoActividad")
    SubTipoActividad = apps.get_model("gestion_agro", "SubTipoActividad")
    CategoriaProducto = apps.get_model("gestion_agro", "CategoriaProducto")

    for modelo in (TipoActividad, SubTipoActividad, CategoriaProducto):
        for fila in modelo.objects.all():
            fila.nombre_es = fila.nombre
            fila.save(update_fields=["nombre_es"])


def revertir_backfill(apps, schema_editor):
    TipoActividad = apps.get_model("gestion_agro", "TipoActividad")
    SubTipoActividad = apps.get_model("gestion_agro", "SubTipoActividad")
    CategoriaProducto = apps.get_model("gestion_agro", "CategoriaProducto")

    for modelo in (TipoActividad, SubTipoActividad, CategoriaProducto):
        modelo.objects.update(nombre_es=None)


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_agro", "0045_categoriaproducto_nombre_es_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_nombre_es, revertir_backfill),
    ]
