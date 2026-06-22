from django.db import migrations, models
import django.utils.translation


class Migration(migrations.Migration):

    dependencies = [
        ("agro", "0009_alter_empresa_unidad_inspeccion_semilla"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="empresa",
            name="lista_precio",
        ),
        migrations.RemoveField(
            model_name="cotizacion_general",
            name="moneda",
        ),
        migrations.RemoveField(
            model_name="cotizacion",
            name="empresa",
        ),
        migrations.RemoveField(
            model_name="cotizacion",
            name="moneda",
        ),
        migrations.DeleteModel(
            name="Cotizacion",
        ),
        migrations.DeleteModel(
            name="Cotizacion_general",
        ),
        migrations.DeleteModel(
            name="Lista_de_precios",
        ),
        migrations.AlterField(
            model_name="profile",
            name="genero",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, to="agro.genero", verbose_name="Género"),
        ),
        migrations.AlterField(
            model_name="profile",
            name="tipo",
            field=models.CharField(choices=[("A", "Administrador")], default="A", max_length=1),
        ),
    ]
