from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_agro', '0034_movimientostock_destino'),
        ('administracion', '0004_facturaventa_item_campos_venta'),
    ]

    operations = [
        migrations.AddField(
            model_name='movimientostock',
            name='factura_venta_item',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='movimientos_stock',
                to='administracion.facturaventaitem',
                verbose_name='Ítem venta',
            ),
        ),
    ]
