"""
Recupera imágenes NDVI de Sentinel-2 vía Copernicus Data Space (CDSE).

Uso:
    python manage.py fetch_ndvi
    python manage.py fetch_ndvi --campo_id=5
    python manage.py fetch_ndvi --dias=20

Cron semanal sugerido:
    0 6 * * 1 /ruta/venv/bin/python /ruta/manage.py fetch_ndvi
"""
import io
import json
import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from gestion_agro.models import Campo, CicloAgricola, AreaCampo
from mapas.models import NDVICaptura


def geojson_union_areas(campo):
    """Retorna un GeoJSON FeatureCollection con TODAS las áreas del campo.
    La API de Sentinel-2 recibe una sola geometría, así que unimos todo en
    una FeatureCollection que _bbox_from_geojson y _mascara_poligono ya saben manejar."""
    areas = AreaCampo.objects.filter(campo=campo, boundary_geojson__isnull=False).order_by("-creado")
    if not areas.exists():
        return None
    features = []
    for a in areas:
        try:
            gj = json.loads(a.boundary_geojson)
            if gj.get("type") == "FeatureCollection":
                features.extend(gj.get("features", []))
            elif gj.get("type") == "Feature":
                features.append(gj)
            else:
                features.append({"type": "Feature", "geometry": gj, "properties": {}})
        except Exception:
            pass
    if not features:
        return None
    return json.dumps({"type": "FeatureCollection", "features": features})

logger = logging.getLogger(__name__)

EVALSCRIPT_NDVI_FLOAT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL"] }],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(s) {
  if ([3, 8, 9, 10, 11].includes(s.SCL)) return [-9999];
  return [(s.B08 - s.B04) / (s.B08 + s.B04 + 0.0001)];
}
"""


def _get_sh_config():
    try:
        from sentinelhub import SHConfig
    except ImportError:
        raise RuntimeError("sentinelhub no instalado. Ejecutá: pip install sentinelhub")

    cfg = SHConfig()
    cfg.sh_client_id     = getattr(settings, "CDSE_CLIENT_ID", "")
    cfg.sh_client_secret = getattr(settings, "CDSE_CLIENT_SECRET", "")
    cfg.sh_base_url      = "https://sh.dataspace.copernicus.eu"
    cfg.sh_token_url     = (
        "https://identity.dataspace.copernicus.eu"
        "/auth/realms/CDSE/protocol/openid-connect/token"
    )
    if not cfg.sh_client_id or not cfg.sh_client_secret:
        raise RuntimeError(
            "Faltan CDSE_CLIENT_ID y CDSE_CLIENT_SECRET en settings.py"
        )
    return cfg


def _bbox_from_geojson(geojson_str):
    """Extrae bounding box de cualquier tipo de GeoJSON (Polygon, Feature, FeatureCollection)."""
    from sentinelhub import BBox, CRS

    gj = json.loads(geojson_str)

    # FeatureCollection → aplanar todas las geometrías
    if gj.get("type") == "FeatureCollection":
        geometries = [f["geometry"] for f in gj.get("features", []) if f.get("geometry")]
    elif gj.get("type") == "Feature":
        geometries = [gj["geometry"]]
    else:
        geometries = [gj]

    coords = []
    for geom in geometries:
        if geom["type"] == "Polygon":
            coords.extend(geom["coordinates"][0])
        elif geom["type"] == "MultiPolygon":
            for ring in geom["coordinates"]:
                coords.extend(ring[0])

    if not coords:
        raise ValueError("GeoJSON no contiene coordenadas válidas")

    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return BBox([min(lngs), min(lats), max(lngs), max(lats)], crs=CRS.WGS84)


def _mascara_poligono(geojson_str, h, w, bbox):
    """Crea una máscara booleana (True = dentro del polígono) usando PIL."""
    from PIL import Image, ImageDraw
    import numpy as np

    gj = json.loads(geojson_str)
    geoms = []
    if gj.get("type") == "FeatureCollection":
        geoms = [f["geometry"] for f in gj.get("features", []) if f.get("geometry")]
    elif gj.get("type") == "Feature":
        geoms = [gj["geometry"]]
    else:
        geoms = [gj]

    rings = []
    for geom in geoms:
        if geom.get("type") == "Polygon":
            rings.append(geom["coordinates"][0])
        elif geom.get("type") == "MultiPolygon":
            for poly in geom["coordinates"]:
                rings.append(poly[0])

    min_lng, min_lat, max_lng, max_lat = bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y

    mask_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask_img)

    for ring in rings:
        pixels = []
        for lng, lat in ring:
            px = int((lng - min_lng) / (max_lng - min_lng) * w)
            py = int((max_lat - lat) / (max_lat - min_lat) * h)
            px = max(0, min(w - 1, px))
            py = max(0, min(h - 1, py))
            pixels.append((px, py))
        if len(pixels) >= 3:
            draw.polygon(pixels, fill=255)

    return np.array(mask_img) > 0


def _procesar_ndvi_array(ndvi_raw, bbox, geojson_str):
    """Recibe array float32. Devuelve (promedio, min, max, nubosidad_pct, png_bytes)."""
    import numpy as np
    from PIL import Image, ImageDraw

    arr = ndvi_raw[:, :, 0] if ndvi_raw.ndim == 3 else ndvi_raw
    h, w = arr.shape

    # Máscara del polígono real
    dentro = _mascara_poligono(geojson_str, h, w, bbox)

    # Nubes: píxeles dentro del polígono con valor ≤ -9999
    mascara_nubes = dentro & (arr <= -9999)
    total_dentro  = int(dentro.sum())
    nubes         = int(mascara_nubes.sum())
    nubosidad     = round(nubes / total_dentro * 100, 1) if total_dentro else 0

    # Válidos: dentro del polígono, sin nubes
    validos = arr[dentro & (arr > -9999)]
    if validos.size == 0:
        return None, None, None, nubosidad, None

    # Si todos los valores son exactamente 0.0 → Sentinel Hub no devolvió imagen real
    if float(validos.max()) == 0.0 and float(validos.min()) == 0.0:
        return None, None, None, 100.0, None

    promedio = round(float(validos.mean()), 4)
    ndvi_min = round(float(validos.min()),  4)
    ndvi_max = round(float(validos.max()),  4)

    # PNG coloreado con condiciones EXCLUSIVAS (orden importa: de mayor a menor)
    rgb = np.zeros((h, w, 4), dtype=np.uint8)
    m = dentro & (arr > -9999)
    # Crítico: NDVI < 0.1 → rojo
    rgb[m & (arr <  0.1)]                    = [220,  50,  50, 220]
    # Estrés: 0.1–0.3 → naranja
    rgb[m & (arr >= 0.1) & (arr <  0.3)]     = [235, 145,  30, 220]
    # Normal: 0.3–0.5 → verde claro
    rgb[m & (arr >= 0.3) & (arr <  0.5)]     = [160, 215,  60, 220]
    # Óptimo: >= 0.5 → verde oscuro
    rgb[m & (arr >= 0.5)]                     = [ 25, 130,  40, 220]
    # Nubes/inválido dentro del polígono → gris semitransparente
    rgb[mascara_nubes]                        = [160, 160, 160, 150]

    img = Image.fromarray(rgb, mode="RGBA")

    # Dibujar el contorno del campo encima con línea blanca gruesa
    draw = ImageDraw.Draw(img)
    min_lng, min_lat = bbox.min_x, bbox.min_y
    max_lng, max_lat = bbox.max_x, bbox.max_y
    gj2 = json.loads(geojson_str)
    geoms2 = []
    if gj2.get("type") == "FeatureCollection":
        geoms2 = [f["geometry"] for f in gj2.get("features", []) if f.get("geometry")]
    elif gj2.get("type") == "Feature":
        geoms2 = [gj2["geometry"]]
    else:
        geoms2 = [gj2]
    for geom2 in geoms2:
        rings2 = []
        if geom2.get("type") == "Polygon":
            rings2 = [geom2["coordinates"][0]]
        elif geom2.get("type") == "MultiPolygon":
            rings2 = [p[0] for p in geom2["coordinates"]]
        for ring2 in rings2:
            pts = []
            for lng, lat in ring2:
                px = int((lng - min_lng) / (max_lng - min_lng) * w)
                py = int((max_lat - lat) / (max_lat - min_lat) * h)
                pts.append((max(0, min(w-1, px)), max(0, min(h-1, py))))
            if len(pts) >= 2:
                draw.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=max(2, w // 200))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return promedio, ndvi_min, ndvi_max, nubosidad, buf.read()


def _fecha_imagen_real(bbox, fecha_desde, fecha_hasta, config):
    """Consulta el catálogo CDSE y retorna la fecha real de la imagen con menos nubes."""
    try:
        from sentinelhub import SentinelHubCatalog, DataCollection, CRS, BBox
        catalog = SentinelHubCatalog(config=config)
        results = catalog.search(
            DataCollection.SENTINEL2_L2A.define_from("s2l2a", service_url=config.sh_base_url),
            bbox=bbox,
            time=(str(fecha_desde), str(fecha_hasta)),
            fields={"include": ["id", "properties.datetime", "properties.eo:cloud_cover"]},
        )
        items = sorted(
            list(results),
            key=lambda x: x.get("properties", {}).get("eo:cloud_cover", 100),
        )
        if items:
            dt_str = items[0]["properties"]["datetime"]  # "2026-05-01T13:22:00Z"
            from datetime import datetime
            return datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
    except Exception:
        pass
    return fecha_hasta


def procesar_campo(campo, fecha_desde, fecha_hasta, config, stdout):
    from sentinelhub import (
        DataCollection, MimeType, SentinelHubRequest, bbox_to_dimensions,
        Geometry, CRS,
    )
    import numpy as np

    # Usar áreas cargadas si existen, sino boundary del campo
    geojson_str = geojson_union_areas(campo) or campo.boundary_geojson
    if not geojson_str:
        stdout.write(f"  SKIP {campo.nombre}: sin contorno ni áreas definidas")
        return

    bbox = _bbox_from_geojson(geojson_str)
    size = bbox_to_dimensions(bbox, resolution=10)
    max_px = 2048  # mayor resolución
    if size[0] > max_px or size[1] > max_px:
        factor = max(size[0], size[1]) / max_px
        size = (int(size[0] / factor), int(size[1] / factor))

    # Usar solo el bbox como geometría para Sentinel (más compatible que MultiPolygon)
    # La máscara de polígonos exactos se aplica después sobre el array
    from sentinelhub import BBox
    geometry = Geometry(
        {"type": "Polygon", "coordinates": [[
            [bbox.min_x, bbox.min_y], [bbox.max_x, bbox.min_y],
            [bbox.max_x, bbox.max_y], [bbox.min_x, bbox.max_y],
            [bbox.min_x, bbox.min_y],
        ]]},
        crs=CRS.WGS84
    )

    # Usamos "mostRecent" para obtener la imagen MÁS NUEVA disponible
    # (leastCC sobre ventanas largas trae imágenes de semanas atrás que no reflejan el estado actual)
    req = SentinelHubRequest(
        evalscript=EVALSCRIPT_NDVI_FLOAT,
        input_data=[SentinelHubRequest.input_data(
            DataCollection.SENTINEL2_L2A.define_from(
                "s2l2a", service_url=config.sh_base_url
            ),
            time_interval=(str(fecha_desde), str(fecha_hasta)),
            mosaicking_order="leastCC",
        )],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        geometry=geometry,
        size=size,
        config=config,
    )

    try:
        ndvi_raw = req.get_data()[0]   # numpy float32 array (H, W, 1)
    except Exception as e:
        stdout.write(f"  ERROR al consultar API: {e}")
        return

    stdout.write(f"  Array shape: {ndvi_raw.shape}, dtype: {ndvi_raw.dtype}")

    promedio, ndvi_min, ndvi_max, nubosidad, png_bytes = _procesar_ndvi_array(
        ndvi_raw, bbox, geojson_str
    )

    stdout.write(f"  Nubosidad: {nubosidad}%")

    if nubosidad > 80:
        stdout.write(f"  Saltando — nubosidad {nubosidad}%")
        return

    if promedio is None:
        stdout.write("  Saltando — sin píxeles válidos")
        return

    # Obtener la fecha real de la imagen (no solo el fin de la ventana)
    fecha_imagen_real = _fecha_imagen_real(bbox, fecha_desde, fecha_hasta, config)
    stdout.write(f"  Fecha real imagen: {fecha_imagen_real}")

    ciclo = (
        CicloAgricola.objects
        .filter(campo=campo, fecha_inicio__lte=fecha_imagen_real, activa=True)
        .order_by("-fecha_inicio")
        .first()
    )

    captura, created = NDVICaptura.objects.update_or_create(
        campo=campo,
        fecha_imagen=fecha_imagen_real,   # fecha real, no fin de ventana
        defaults=dict(
            ciclo=ciclo,
            origen=NDVICaptura.Origen.AUTO,
            ndvi_promedio=promedio,
            ndvi_min=ndvi_min,
            ndvi_max=ndvi_max,
            nubosidad_pct=nubosidad,
            fecha_proceso=timezone.now(),
        ),
    )

    if png_bytes:
        captura.imagen_png.save(
            f"ndvi_{campo.id}_{fecha_imagen_real}.png",
            ContentFile(png_bytes, name=f"ndvi_{campo.id}_{fecha_hasta}.png"),
            save=True,
        )

    accion = "Creada" if created else "Actualizada"
    stdout.write(
        f"  {accion} — NDVI avg={promedio:.3f} min={ndvi_min:.3f} max={ndvi_max:.3f} nubes={nubosidad}%"
    )


class Command(BaseCommand):
    help = "Recupera imágenes NDVI de Sentinel-2 (CDSE) para cada campo con contorno definido"

    def add_arguments(self, parser):
        parser.add_argument("--campo_id", type=int, default=None, help="Procesar solo este campo")
        parser.add_argument("--dias",     type=int, default=10,   help="Ventana de días hacia atrás (default: 10 — captura la imagen más clara de los últimos 10 días)")

    def handle(self, *args, **options):
        try:
            config = _get_sh_config()
        except RuntimeError as e:
            self.stderr.write(str(e))
            return

        try:
            import numpy  # noqa
            from PIL import Image  # noqa
        except ImportError:
            self.stderr.write("Faltan dependencias: pip install sentinelhub numpy Pillow")
            return

        campo_id = options["campo_id"]
        dias     = options["dias"]

        qs = Campo.objects.filter(
            models.Q(areas__boundary_geojson__isnull=False) |
            models.Q(boundary_geojson__isnull=False)
        ).exclude(boundary_geojson="").distinct()
        if campo_id:
            qs = qs.filter(id=campo_id)

        if not qs.exists():
            self.stdout.write("No hay campos con contorno definido.")
            return

        fecha_hasta  = date.today()
        fecha_desde  = fecha_hasta - timedelta(days=dias)

        self.stdout.write(
            f"Procesando {qs.count()} campo(s) — período {fecha_desde} → {fecha_hasta}"
        )

        for campo in qs:
            self.stdout.write(f"\n→ {campo.nombre}")
            try:
                procesar_campo(campo, fecha_desde, fecha_hasta, config, self.stdout)
            except Exception as e:
                self.stderr.write(f"  ERROR inesperado: {e}")
                logger.exception("fetch_ndvi error campo %s", campo.id)

        self.stdout.write("\nListo.")
