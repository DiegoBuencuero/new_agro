from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0006_facturaventaitem_schema_fix'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Cobro',
            new_name='Recibo',
        ),
        migrations.RenameModel(
            old_name='AplicacionCobro',
            new_name='AplicacionRecibo',
        ),
    ]
