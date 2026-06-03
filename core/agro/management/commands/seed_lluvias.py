"""
Carga datos de lluvia para todos los campos de una empresa.
Combina datos reales de Open-Meteo (mayo-junio 2026) con datos
climatológicamente realistas para el Alto Uruguai, RS/SC.
"""
import math
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand

# Datos reales Open-Meteo (2026-05-07 a 2026-06-02)
DATOS_REALES = {
    "2026-05-07": 0.00, "2026-05-08": 27.80, "2026-05-09": 0.80,
    "2026-05-10": 0.00, "2026-05-11": 0.00,  "2026-05-12": 0.00,
    "2026-05-13": 0.00, "2026-05-14": 0.00,  "2026-05-15": 1.60,
    "2026-05-16": 1.70, "2026-05-17": 1.00,  "2026-05-18": 1.30,
    "2026-05-19": 0.80, "2026-05-20": 0.00,  "2026-05-21": 0.00,
    "2026-05-22": 2.00, "2026-05-23": 0.40,  "2026-05-24": 0.00,
    "2026-05-25": 3.80, "2026-05-26": 19.60, "2026-05-27": 0.20,
    "2026-05-28": 0.00, "2026-05-29": 0.40,  "2026-05-30": 14.40,
    "2026-05-31": 0.90, "2026-06-01": 0.00,  "2026-06-02": 0.00,
}

# Precipitación media mensual (mm/mes) para Alto Uruguai, RS — climatología histórica
MEDIA_MENSUAL = {
    1: 175, 2: 162, 3: 150, 4: 145, 5: 128,
    6: 132, 7: 140, 8: 118, 9: 168, 10: 188,
    11: 178, 12: 170,
}


def _lluvia_dia(fecha, seed_campo):
    """Genera lluvia diaria creíble usando la climatología del mes."""
    clave = str(fecha)
    if clave in DATOS_REALES:
        return round(DATOS_REALES[clave], 1)

    random.seed(hash((fecha.toordinal(), seed_campo)) & 0xFFFFFF)
    media_mes = MEDIA_MENSUAL[fecha.month]
    dias_mes = 30
    # Probabilidad de lluvia ese día (~60% de días con lluvia en la región)
    if random.random() > 0.60:
        return 0.0
    # Distribución exponencial — pocos días con mucha lluvia
    media_dia = media_mes / (dias_mes * 0.60)
    lluvia = random.expovariate(1 / media_dia)
    return round(min(lluvia, 80.0), 1)  # cap en 80mm/día


class Command(BaseCommand):
    help = "Carga datos de lluvia (climatología + datos reales) para todos los campos"

    def add_arguments(self, parser):
        parser.add_argument("--empresa", type=str, default="Agroinnova")
        parser.add_argument("--desde",   type=str, default="2025-06-01")

    def handle(self, *args, **options):
        from agro.models import Empresa
        from gestion_agro.models import Campo
        from mapas.models import MedicionCampo, VariableAnalitica

        try:
            empresa = Empresa.objects.get(nombre=options["empresa"])
        except Empresa.DoesNotExist:
            self.stderr.write(f"Empresa '{options['empresa']}' no encontrada.")
            return

        var, _ = VariableAnalitica.objects.get_or_create(
            nombre="Precipitación", tipo="clima",
            defaults={"unidad": "mm"},
        )

        campos = Campo.objects.filter(empresa=empresa)
        fecha_desde = date.fromisoformat(options["desde"])
        fecha_hasta = date.today()

        for campo in campos:
            # Borrar registros anteriores de lluvia para este campo
            eliminados = MedicionCampo.objects.filter(campo=campo, variable=var).delete()[0]
            if eliminados:
                self.stdout.write(f"  {campo.nombre}: {eliminados} registros anteriores borrados")

            bulk = []
            fecha = fecha_desde
            total_mm = 0.0
            while fecha <= fecha_hasta:
                mm = _lluvia_dia(fecha, campo.id)
                total_mm += mm
                bulk.append(MedicionCampo(
                    campo=campo,
                    variable=var,
                    fecha=fecha,
                    promedio=mm,
                    minimo=None,
                    maximo=None,
                ))
                fecha += timedelta(days=1)

            MedicionCampo.objects.bulk_create(bulk)
            dias_reales = len([f for f in DATOS_REALES if fecha_desde <= date.fromisoformat(f) <= fecha_hasta])
            self.stdout.write(self.style.SUCCESS(
                f"  {campo.nombre}: {len(bulk)} días cargados | "
                f"{dias_reales} con datos reales | total {total_mm:.0f} mm"
            ))

        self.stdout.write(self.style.SUCCESS("Seed de lluvias completado."))
