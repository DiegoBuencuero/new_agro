from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_agro', '0033_remove_camposcosecha_kg_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='movimientostock',
            name='destino',
            field=models.CharField(
                blank=True,
                choices=[('M', 'Multiplicacion'), ('C', 'Consumo')],
                max_length=1,
                null=True,
                verbose_name='Destino',
            ),
        ),
    ]
