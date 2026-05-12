from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0004_facturaventa_item_campos_venta'),
        ('auth', '__first__'),
    ]

    operations = [
        # Renombrar nfe_numero → numero
        migrations.RenameField(
            model_name='facturaventa',
            old_name='nfe_numero',
            new_name='numero',
        ),
        # Eliminar columnas que ya no están en el modelo
        migrations.RemoveField(model_name='facturaventa', name='nfe_serie'),
        migrations.RemoveField(model_name='facturaventa', name='total'),
        migrations.RemoveField(model_name='facturaventa', name='entrega'),
        # Agregar usuario
        migrations.AddField(
            model_name='facturaventa',
            name='usuario',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='auth.user',
                verbose_name='Usuario que creó',
            ),
        ),
    ]
