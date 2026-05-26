import datetime
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0009_pago_numero_fecha_medioPago"),
    ]

    operations = [
        # 1. Add creado
        migrations.AddField(
            model_name="recibo",
            name="creado",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        # 2. Add numero
        migrations.AddField(
            model_name="recibo",
            name="numero",
            field=models.PositiveIntegerField(default=0, verbose_name="N° recibo"),
        ),
        # 3. Add medio_cobro
        migrations.AddField(
            model_name="recibo",
            name="medio_cobro",
            field=models.CharField(
                choices=[
                    ("TRF", "Transferencia"),
                    ("CHQ", "Cheque"),
                    ("EFE", "Efectivo"),
                    ("DEB", "Débito automático"),
                ],
                default="TRF",
                max_length=3,
                verbose_name="Medio de cobro",
            ),
        ),
        # 4. Add referencia
        migrations.AddField(
            model_name="recibo",
            name="referencia",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="Referencia"),
        ),
        # 5. Add fecha_nueva (nullable DateField)
        migrations.AddField(
            model_name="recibo",
            name="fecha_nueva",
            field=models.DateField(null=True, blank=True),
        ),
        # 6. Copy old fecha (DateTimeField) → fecha_nueva
        migrations.RunSQL(
            "UPDATE administracion_recibo SET fecha_nueva = DATE(fecha)",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 7. Remove old fecha
        migrations.RemoveField(model_name="recibo", name="fecha"),
        # 8. Rename
        migrations.RenameField(model_name="recibo", old_name="fecha_nueva", new_name="fecha"),
        # 9. Make non-nullable
        migrations.AlterField(
            model_name="recibo",
            name="fecha",
            field=models.DateField(default=datetime.date.today, verbose_name="Fecha"),
        ),
        # 10. Update ordering
        migrations.AlterModelOptions(
            name="recibo",
            options={
                "ordering": ["-fecha", "-numero"],
                "verbose_name": "Recibo",
                "verbose_name_plural": "Recibos",
            },
        ),
    ]
