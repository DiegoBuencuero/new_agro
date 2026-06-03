"""
Genera análisis de suelo simulados (N, P, K, MO, pH) para el campo iBICUI
usando las coordenadas de los shapefiles de KCL y GESSO como base espacial.
"""
import json
import math
import random
from datetime import date
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

CARPETA = Path("/home/diego/Área de trabalho/ibicui")

# Variables: (nombre, unidad, rango_min, rango_max, tipo)
VARIABLES = [
    ("K",  "cmol/dm³", 0.08, 0.50, "suelo"),
    ("P",  "mg/dm³",   4.0,  35.0, "suelo"),
    ("MO", "g/dm³",    18.0, 52.0, "suelo"),
    ("pH", "",         4.5,  6.2,  "suelo"),
    ("N",  "g/kg",     0.8,  2.5,  "suelo"),
]


def _noise(seed, x, y, scale=0.003):
    """Pseudorandom smooth noise basado en posición — sin dependencias extra."""
    hx = math.sin(x / scale + seed * 7.3) * 43758.5453
    hy = math.sin(y / scale + seed * 13.7) * 12345.6789
    hxy = math.sin((x + y) / scale * 1.7 + seed * 3.1) * 98765.4321
    return (hx - math.floor(hx) + hy - math.floor(hy) + hxy - math.floor(hxy)) / 3.0


def _generar_valor(variable, lng, lat, kcl_rate_norm, gesso_rate_norm):
    """Genera un valor creíble para la variable en la posición dada."""
    seed_map = {"K": 1, "P": 2, "MO": 3, "pH": 4, "N": 5}
    seed = seed_map.get(variable, 0)
    n = _noise(seed, lng, lat)

    if variable == "K":
        # Alta dosis KCL → suelo bajo en K (necesita corrección)
        base = 0.48 - kcl_rate_norm * 0.35
        val = base + (n - 0.5) * 0.06
    elif variable == "P":
        base = 8 + n * 24
        val = base + (n - 0.5) * 3
    elif variable == "MO":
        base = 25 + n * 22
        val = base + (n - 0.5) * 4
    elif variable == "pH":
        # Alta dosis GESSO → pH actual bajo (por eso necesita corrección)
        base = 5.9 - gesso_rate_norm * 1.2
        val = base + (n - 0.5) * 0.25
    elif variable == "N":
        mo = 25 + n * 22  # consistent with MO
        val = mo * 0.048 + (n - 0.5) * 0.15
    else:
        val = n

    # Clamp a rango esperado
    rango = {v[0]: (v[2], v[3]) for v in VARIABLES}
    lo, hi = rango.get(variable, (0, 1))
    return round(max(lo, min(hi, val)), 3)


class Command(BaseCommand):
    help = "Carga análisis de suelo simulados (N, P, K, MO, pH) para el campo iBICUI"

    def add_arguments(self, parser):
        parser.add_argument("--campo", type=str, default="iBICUI")
        parser.add_argument("--empresa", type=str, default="Agroinnova")

    def handle(self, *args, **options):
        import shapefile
        from django.utils import timezone
        from agro.models import Empresa
        from gestion_agro.models import Campo
        from mapas.models import ArchivoAnalitico, VariableAnalitica
        from mapas.aux_raster import colorear_geojson, rasterizar_a_png, calcular_bbox

        try:
            empresa = Empresa.objects.get(nombre=options["empresa"])
        except Empresa.DoesNotExist:
            self.stderr.write(f"Empresa '{options['empresa']}' no encontrada.")
            return

        try:
            campo = Campo.objects.get(nombre=options["campo"], empresa=empresa)
        except Campo.DoesNotExist:
            self.stderr.write(f"Campo '{options['campo']}' no encontrado.")
            return

        self.stdout.write(f"Campo: {campo} | Empresa: {empresa}")

        # Leer puntos de ambas zonas KCL (tienen la cobertura más densa)
        puntos = []  # [(lng, lat, kcl_rate, gesso_rate)]

        kcl_rates_2  = {}
        gesso_rates_2 = {}
        kcl_rates_3  = {}
        gesso_rates_3 = {}

        for nombre, dest in [("IBICUI 2_KCL", kcl_rates_2), ("IBICUI 3_KCL", kcl_rates_3)]:
            path = CARPETA / nombre
            sf = shapefile.Reader(str(path))
            for sr in sf.shapeRecords():
                lng, lat = sr.shape.points[0]
                key = (round(lng, 7), round(lat, 7))
                dest[key] = sr.record["rate"]

        for nombre, dest in [("IBICUI 2_GESSO", gesso_rates_2), ("IBICUI 3_GESSO", gesso_rates_3)]:
            path = CARPETA / nombre
            sf = shapefile.Reader(str(path))
            for sr in sf.shapeRecords():
                lng, lat = sr.shape.points[0]
                key = (round(lng, 7), round(lat, 7))
                dest[key] = sr.record["rate"]

        # Unir puntos de zona 2 y zona 3
        all_kcl = {**kcl_rates_2, **kcl_rates_3}
        all_gesso = {**gesso_rates_2, **gesso_rates_3}

        kcl_min, kcl_max = 100.0, 400.0
        gesso_min, gesso_max = 0.0, 2700.0

        for key, kcl_rate in all_kcl.items():
            lng, lat = key
            gesso_rate = all_gesso.get(key, 0.0)
            kcl_norm   = (kcl_rate - kcl_min) / (kcl_max - kcl_min)
            gesso_norm = (gesso_rate - gesso_min) / (gesso_max - gesso_min)
            puntos.append((lng, lat, kcl_norm, gesso_norm))

        self.stdout.write(f"Puntos totales: {len(puntos)}")

        # Tomar muestra uniforme (max 800 puntos para no generar un archivo enorme)
        random.seed(42)
        if len(puntos) > 800:
            puntos = random.sample(puntos, 800)
            self.stdout.write(f"Muestreados: {len(puntos)}")

        # Crear VariableAnalitica y ArchivoAnalitico para cada variable
        user = empresa.profile_set.first().user if hasattr(empresa, 'profile_set') else None

        for var_nombre, unidad, rmin, rmax, tipo in VARIABLES:
            var, _ = VariableAnalitica.objects.get_or_create(
                nombre=var_nombre, tipo=tipo,
                defaults={"unidad": unidad, "rango_minimo": rmin, "rango_maximo": rmax},
            )

            features = []
            for lng, lat, kcl_norm, gesso_norm in puntos:
                val = _generar_valor(var_nombre, lng, lat, kcl_norm, gesso_norm)
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lng, lat]},
                    "properties": {"v": val, var_nombre: val},
                })

            geojson = {"type": "FeatureCollection", "features": features}
            geojson, leyenda, stats = colorear_geojson(geojson, columna="v")
            bbox = calcular_bbox(features)

            try:
                png_bytes = rasterizar_a_png(geojson, bbox)
            except Exception as e:
                self.stdout.write(f"  WARN rasterizar {var_nombre}: {e}")
                png_bytes = None

            geojson_bytes = json.dumps(geojson, separators=(",", ":")).encode()
            archivo_content = ContentFile(geojson_bytes, name=f"suelo_ibicui_{var_nombre.lower()}.geojson")

            registro = ArchivoAnalitico.objects.create(
                campo=campo,
                variable=var,
                cargado_por=user,
                tipo_archivo="geojson",
                estado="procesado" if png_bytes else "pendiente",
                bbox=bbox,
                leyenda=leyenda,
                estadisticas=stats,
            )
            registro.archivo.save(f"suelo_ibicui_{var_nombre.lower()}.geojson", archivo_content, save=True)

            if png_bytes:
                registro.imagen_png.save(
                    f"suelo_ibicui_{campo.id}_{var_nombre.lower()}.png",
                    ContentFile(png_bytes),
                    save=True,
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {var_nombre}: {len(features)} puntos | "
                    f"min={stats.get('min')} max={stats.get('max')} prom={stats.get('prom')} | "
                    f"PNG={'sí' if png_bytes else 'no'}"
                )
            )

        self.stdout.write(self.style.SUCCESS("Seed de suelo iBICUI completado."))
