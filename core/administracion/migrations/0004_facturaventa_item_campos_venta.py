from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0003_cobro_cliente_cobro_empresa_aplicacioncobro_cobro_and_more'),
        ('agro', '0001_initial'),
        ('gestion_agro', '0034_movimientostock_destino'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturaventaitem',
            name='deposito_origen',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='gestion_agro.deposito',
                verbose_name='Depósito origen',
            ),
        ),
        migrations.AddField(
            model_name='facturaventaitem',
            name='destino',
            field=models.CharField(
                blank=True, null=True,
                choices=[('M', 'Semilla (Multiplicación)'), ('C', 'Consumo')],
                max_length=1,
                verbose_name='Destino',
            ),
        ),
        migrations.AddField(
            model_name='facturaventaitem',
            name='um',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='agro.unidad',
                verbose_name='Unidad de medida',
            ),
        ),
    ]
