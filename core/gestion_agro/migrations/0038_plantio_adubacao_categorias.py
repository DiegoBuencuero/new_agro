from django.db import migrations


def add_plantio_adubacao_categorias(apps, schema_editor):
    TipoActividad = apps.get_model("gestion_agro", "TipoActividad")
    CategoriaProducto = apps.get_model("gestion_agro", "CategoriaProducto")
    TipoActividadCategoriaProducto = apps.get_model("gestion_agro", "TipoActividadCategoriaProducto")

    tipo = TipoActividad.objects.filter(tipo="P").first()
    if not tipo:
        return

    for cat_codigo in ("SEM", "FER"):
        try:
            cat = CategoriaProducto.objects.get(codigo=cat_codigo)
        except CategoriaProducto.DoesNotExist:
            continue
        TipoActividadCategoriaProducto.objects.get_or_create(
            tipo_actividad=tipo,
            subtipo_actividad=None,
            categoria_producto=cat,
            defaults={"activo": True},
        )


def remove_plantio_adubacao_categorias(apps, schema_editor):
    TipoActividad = apps.get_model("gestion_agro", "TipoActividad")
    TipoActividadCategoriaProducto = apps.get_model("gestion_agro", "TipoActividadCategoriaProducto")
    tipo = TipoActividad.objects.filter(tipo="P").first()
    if tipo:
        TipoActividadCategoriaProducto.objects.filter(tipo_actividad=tipo).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_agro", "0037_cicloagricola_area"),
    ]

    operations = [
        migrations.RunPython(
            add_plantio_adubacao_categorias,
            remove_plantio_adubacao_categorias,
        ),
    ]
