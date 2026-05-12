from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0005_facturaventa_schema_fix'),
        ('gestion_agro', '0035_movimientostock_factura_venta_item'),
    ]

    operations = [
        # Eliminar columnas que ya no están en el modelo
        migrations.RemoveField(model_name='facturaventaitem', name='descripcion'),
        migrations.RemoveField(model_name='facturaventaitem', name='subtotal'),
        # Agregar producto
        migrations.AddField(
            model_name='facturaventaitem',
            name='producto',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='gestion_agro.producto',
                default=1,  # temporal para registros existentes
            ),
            preserve_default=False,
        ),
    ]
