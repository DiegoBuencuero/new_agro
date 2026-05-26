import datetime
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0008_rename_cobro_id_to_recibo_id"),
    ]

    operations = [
        # 1. Add creado (timestamp, replaces old fecha auto_now_add)
        migrations.AddField(
            model_name="pago",
            name="creado",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        # 2. Add numero
        migrations.AddField(
            model_name="pago",
            name="numero",
            field=models.PositiveIntegerField(default=0, verbose_name="N° orden"),
        ),
        # 3. Add medio_pago
        migrations.AddField(
            model_name="pago",
            name="medio_pago",
            field=models.CharField(
                choices=[
                    ("TRF", "Transferencia"),
                    ("CHQ", "Cheque"),
                    ("EFE", "Efectivo"),
                    ("DEB", "Débito automático"),
                ],
                default="TRF",
                max_length=3,
                verbose_name="Medio de pago",
            ),
        ),
        # 4. Add referencia
        migrations.AddField(
            model_name="pago",
            name="referencia",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="Referencia"),
        ),
        # 5. Add new fecha (DateField) as nullable first
        migrations.AddField(
            model_name="pago",
            name="fecha_nueva",
            field=models.DateField(null=True, blank=True),
        ),
        # 6. Data migration: copy old fecha (DateTimeField) → fecha_nueva (DateField)
        migrations.RunSQL(
            "UPDATE administracion_pago SET fecha_nueva = DATE(fecha)",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 7. Remove old fecha
        migrations.RemoveField(model_name="pago", name="fecha"),
        # 8. Rename fecha_nueva → fecha
        migrations.RenameField(model_name="pago", old_name="fecha_nueva", new_name="fecha"),
        # 9. Make fecha non-nullable with default
        migrations.AlterField(
            model_name="pago",
            name="fecha",
            field=models.DateField(default=datetime.date.today, verbose_name="Fecha"),
        ),
        # 10. Update ordering in Meta
        migrations.AlterModelOptions(
            name="pago",
            options={
                "ordering": ["-fecha", "-numero"],
                "verbose_name": "Pago",
                "verbose_name_plural": "Pagos",
            },
        ),
    ]
