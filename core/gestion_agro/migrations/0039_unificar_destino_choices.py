from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_agro", "0038_plantio_adubacao_categorias"),
    ]

    operations = [
        migrations.AlterField(
            model_name="movimientostock",
            name="destino",
            field=models.CharField(
                blank=True,
                choices=[("M", "Semilla (Multiplicación)"), ("C", "Consumo")],
                max_length=1,
                null=True,
                verbose_name="Destino",
            ),
        ),
    ]
