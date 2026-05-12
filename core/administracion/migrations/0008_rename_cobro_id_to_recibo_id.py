from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0007_rename_cobro_to_recibo'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aplicacionrecibo',
            old_name='cobro',
            new_name='recibo',
        ),
    ]
