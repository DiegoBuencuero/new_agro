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

    tipo_aplicacion, _c = TipoActividad.objects.get_or_create(
        nombre="Aplicación",
        defaults={
            "tipo": "A", "activo": True,
            "abre_fase": False, "cierra_fase": False,
            "requiere_insumo": True, "requiere_mo": True, "requiere_maq": True,
            "requiere_cosecha": False, "requiere_vist": False,
        },
    )
    subtipo_limpa, _c = SubTipoActividad.objects.get_or_create(
        tipo_actividad=tipo_aplicacion,
        codigo="LP",
        defaults={"nombre": "Limpa", "activo": True, "abre_fase": True, "cierra_fase": False},
    )

    tipo_siembra, _c = TipoActividad.objects.get_or_create(
        nombre="Siembra",
        defaults={
            "tipo": "S", "activo": True,
            "abre_fase": True, "cierra_fase": False,
            "requiere_insumo": True, "requiere_mo": True, "requiere_maq": True,
            "requiere_cosecha": False, "requiere_vist": False,
        },
    )
    subtipo_sp, _c = SubTipoActividad.objects.get_or_create(
        tipo_actividad=tipo_siembra,
        codigo="SP",
        defaults={"nombre": "Cultivo Principal", "activo": True, "abre_fase": True, "cierra_fase": False},
    )

    cat_fun, _c = CategoriaProducto.objects.get_or_create(
        codigo="FUN", defaults={"nombre": "Fungicida", "es_semilla": False}
    )
    cat_ins, _c = CategoriaProducto.objects.get_or_create(
        codigo="INS", defaults={"nombre": "Insecticida", "es_semilla": False}
    )
    cat_fer, _c = CategoriaProducto.objects.get_or_create(
        codigo="FER", defaults={"nombre": "Fertilizante", "es_semilla": False}
    )

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
