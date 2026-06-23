from django.db import migrations


def add_catalogo(apps, schema_editor):
    TipoActividad = apps.get_model("gestion_agro", "TipoActividad")
    SubTipoActividad = apps.get_model("gestion_agro", "SubTipoActividad")
    CategoriaProducto = apps.get_model("gestion_agro", "CategoriaProducto")
    TipoActividadCategoriaProducto = apps.get_model("gestion_agro", "TipoActividadCategoriaProducto")

    tipo_inspeccion, _c = TipoActividad.objects.get_or_create(
        nombre="Inspeccion",
        defaults={"tipo": "M", "activo": True, "requiere_inspeccion": True},
    )

    tipo_aplicacion = TipoActividad.objects.get(nombre="Aplicación")
    subtipo_limpa, _c = SubTipoActividad.objects.get_or_create(
        tipo_actividad=tipo_aplicacion,
        codigo="LP",
        defaults={"nombre": "Limpa", "activo": True, "abre_fase": True, "cierra_fase": False},
    )

    tipo_siembra = TipoActividad.objects.get(nombre="Siembra")
    subtipo_sp = SubTipoActividad.objects.get(tipo_actividad=tipo_siembra, codigo="SP")

    cat_fun = CategoriaProducto.objects.get(codigo="FUN")
    cat_ins = CategoriaProducto.objects.get(codigo="INS")
    cat_fer = CategoriaProducto.objects.get(codigo="FER")

    relaciones_nuevas = [
        (tipo_aplicacion, None, cat_fun),
        (tipo_aplicacion, None, cat_ins),
        (tipo_siembra, subtipo_sp, cat_fer),
    ]
    for tipo, subtipo, categoria in relaciones_nuevas:
        TipoActividadCategoriaProducto.objects.get_or_create(
            tipo_actividad=tipo,
            subtipo_actividad=subtipo,
            categoria_producto=categoria,
            defaults={"activo": True},
        )


def remove_catalogo(apps, schema_editor):
    TipoActividad = apps.get_model("gestion_agro", "TipoActividad")
    SubTipoActividad = apps.get_model("gestion_agro", "SubTipoActividad")
    CategoriaProducto = apps.get_model("gestion_agro", "CategoriaProducto")
    TipoActividadCategoriaProducto = apps.get_model("gestion_agro", "TipoActividadCategoriaProducto")

    try:
        tipo_aplicacion = TipoActividad.objects.get(nombre="Aplicación")
        tipo_siembra = TipoActividad.objects.get(nombre="Siembra")
        subtipo_sp = SubTipoActividad.objects.get(tipo_actividad=tipo_siembra, codigo="SP")
        cat_fun = CategoriaProducto.objects.get(codigo="FUN")
        cat_ins = CategoriaProducto.objects.get(codigo="INS")
        cat_fer = CategoriaProducto.objects.get(codigo="FER")

        TipoActividadCategoriaProducto.objects.filter(
            tipo_actividad=tipo_aplicacion, subtipo_actividad__isnull=True, categoria_producto=cat_fun
        ).delete()
        TipoActividadCategoriaProducto.objects.filter(
            tipo_actividad=tipo_aplicacion, subtipo_actividad__isnull=True, categoria_producto=cat_ins
        ).delete()
        TipoActividadCategoriaProducto.objects.filter(
            tipo_actividad=tipo_siembra, subtipo_actividad=subtipo_sp, categoria_producto=cat_fer
        ).delete()

        SubTipoActividad.objects.filter(tipo_actividad=tipo_aplicacion, codigo="LP").delete()
    except (TipoActividad.DoesNotExist, SubTipoActividad.DoesNotExist, CategoriaProducto.DoesNotExist):
        pass

    TipoActividad.objects.filter(nombre="Inspeccion").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_agro", "0043_categoria_producto_final_semilla"),
    ]

    operations = [
        migrations.RunPython(add_catalogo, remove_catalogo),
    ]
