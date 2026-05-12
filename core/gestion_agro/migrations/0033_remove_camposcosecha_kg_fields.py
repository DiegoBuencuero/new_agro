from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_agro', '0032_es_semilla_cosecha_movimiento'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='camposcosecha',
            name='kg_semilla',
        ),
        migrations.RemoveField(
            model_name='camposcosecha',
            name='kg_consumo',
        ),
    ]
