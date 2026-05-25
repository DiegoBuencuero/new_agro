import io
import json
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from gestion_agro.models import CicloAgricola
from mapas.models import CapturaSatelite, IndiceVegetacion
from mapas.aux_geo import geojson_union_areas

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
        raise RuntimeError("Faltan CDSE_CLIENT_ID y CDSE_CLIENT_SECRET en settings.py")
    return cfg


def _bbox_from_geojson(geojson_str):
    from sentinelhub import BBox, CRS

    gj = json.loads(geojson_str)

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


def _extraer_rings(geojson_str):
    """Devuelve lista de rings (lista de [lng, lat]) desde cualquier GeoJSON."""
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
    return rings


def _dibujar_borde(draw, rings, bbox, h, w, color, ancho):
    min_lng, min_lat = bbox.min_x, bbox.min_y
    max_lng, max_lat = bbox.max_x, bbox.max_y

    for ring in rings:
        pts = []
        for lng, lat in ring:
            px = int((lng - min_lng) / (max_lng - min_lng) * w)
            py = int((max_lat - lat) / (max_lat - min_lat) * h)
            pts.append((max(0, min(w - 1, px)), max(0, min(h - 1, py))))
        if len(pts) >= 2:
            draw.line(pts + [pts[0]], fill=color, width=ancho)


def _procesar_ndvi_array(ndvi_raw, bbox, area_geojson_str, ciclo_geojson_str=None):
    """
    Calcula NDVI y genera imagen PNG.

    area_geojson_str  — geometría del campo/áreas (AOI, máscara y borde blanco)
    ciclo_geojson_str — contorno del ciclo activo; si existe se dibuja en amarillo
    """
    import numpy as np
    from PIL import Image, ImageDraw

    arr = ndvi_raw[:, :, 0] if ndvi_raw.ndim == 3 else ndvi_raw
    h, w = arr.shape

    dentro = _mascara_poligono(area_geojson_str, h, w, bbox)

    mascara_nubes = dentro & (arr <= -9999)
    total_dentro  = int(dentro.sum())
    nubes         = int(mascara_nubes.sum())
    nubosidad     = round(nubes / total_dentro * 100, 1) if total_dentro else 0

    validos = arr[dentro & (arr > -9999)]
    if validos.size == 0:
        return None, None, None, nubosidad, None

    if float(validos.max()) == 0.0 and float(validos.min()) == 0.0:
        return None, None, None, 100.0, None

    promedio = round(float(validos.mean()), 4)
    ndvi_min = round(float(validos.min()),  4)
    ndvi_max = round(float(validos.max()),  4)

    rgb = np.zeros((h, w, 4), dtype=np.uint8)
    m = dentro & (arr > -9999)
    rgb[m & (arr <  0.1)]                = [220,  50,  50, 220]
    rgb[m & (arr >= 0.1) & (arr < 0.3)]  = [235, 145,  30, 220]
    rgb[m & (arr >= 0.3) & (arr < 0.5)]  = [160, 215,  60, 220]
    rgb[m & (arr >= 0.5)]                = [ 25, 130,  40, 220]
    rgb[mascara_nubes]                   = [160, 160, 160, 150]

    img  = Image.fromarray(rgb, mode="RGBA")
    draw = ImageDraw.Draw(img)

    ancho_borde = max(2, w // 200)

    # Borde blanco del campo/áreas
    _dibujar_borde(draw, _extraer_rings(area_geojson_str), bbox, h, w,
                   color=(255, 255, 255, 255), ancho=ancho_borde)

    # Borde amarillo del ciclo activo (siempre visible si existe)
    if ciclo_geojson_str:
        try:
            _dibujar_borde(draw, _extraer_rings(ciclo_geojson_str), bbox, h, w,
                           color=(255, 220, 0, 255), ancho=max(3, w // 150))
        except Exception:
            logger.warning("No se pudo dibujar el contorno del ciclo")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return promedio, ndvi_min, ndvi_max, nubosidad, buf.read()


def _buscar_mejor_imagen(bbox, fecha_desde, fecha_hasta, config, max_nubes=10):
    from datetime import datetime
    try:
        from sentinelhub import SentinelHubCatalog, DataCollection
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
            best      = items[0]
            cloud_pct = best.get("properties", {}).get("eo:cloud_cover", 100)
            dt_str    = best["properties"]["datetime"]
            fecha     = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
            if cloud_pct <= max_nubes:
                return fecha, round(cloud_pct, 1)
            return None, round(cloud_pct, 1)
    except Exception:
        pass
    return None, None


def _fecha_imagen_real(bbox, fecha_desde, fecha_hasta, config):
    fecha, _ = _buscar_mejor_imagen(bbox, fecha_desde, fecha_hasta, config)
    return fecha or fecha_hasta


def procesar_campo(campo, fecha_desde, fecha_hasta, config, stdout):
    from sentinelhub import (
        DataCollection, MimeType, SentinelHubRequest,
        bbox_to_dimensions, Geometry, CRS,
    )

    # AOI: siempre el campo completo (unión de áreas o contorno del campo)
    geojson_str = geojson_union_areas(campo) or campo.contorno
    if not geojson_str:
        stdout.write(f"  SKIP {campo.nombre}: sin contorno ni áreas definidas")
        return

    bbox = _bbox_from_geojson(geojson_str)
    size = bbox_to_dimensions(bbox, resolution=10)
    max_px = 2048
    if size[0] > max_px or size[1] > max_px:
        factor = max(size[0], size[1]) / max_px
        size   = (int(size[0] / factor), int(size[1] / factor))

    geometry = Geometry(
        {"type": "Polygon", "coordinates": [[
            [bbox.min_x, bbox.min_y], [bbox.max_x, bbox.min_y],
            [bbox.max_x, bbox.max_y], [bbox.min_x, bbox.max_y],
            [bbox.min_x, bbox.min_y],
        ]]},
        crs=CRS.WGS84,
    )

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
        ndvi_raw = req.get_data()[0]
    except Exception as e:
        stdout.write(f"  ERROR al consultar API: {e}")
        return

    stdout.write(f"  Array shape: {ndvi_raw.shape}, dtype: {ndvi_raw.dtype}")

    fecha_imagen_real = _fecha_imagen_real(bbox, fecha_desde, fecha_hasta, config)
    stdout.write(f"  Fecha real imagen: {fecha_imagen_real}")

    # Ciclo activo en la fecha de la imagen
    ciclo = (
        CicloAgricola.objects
        .filter(campo=campo, fecha_inicio__lte=fecha_imagen_real, activa=True)
        .order_by("-fecha_inicio")
        .first()
    )

    # Contorno del ciclo para overlay (amarillo en el PNG)
    ciclo_geojson = ciclo.contorno if (ciclo and ciclo.contorno) else None
    if ciclo_geojson:
        stdout.write(f"  Ciclo activo con contorno: {ciclo}")
    elif ciclo:
        stdout.write(f"  Ciclo activo sin contorno: {ciclo}")

    promedio, ndvi_min, ndvi_max, nubosidad, png_bytes = _procesar_ndvi_array(
        ndvi_raw, bbox, geojson_str, ciclo_geojson_str=ciclo_geojson
    )

    stdout.write(f"  Nubosidad: {nubosidad}%")

    if nubosidad > 80:
        stdout.write(f"  Saltando — nubosidad {nubosidad}%")
        return

    if promedio is None:
        stdout.write("  Saltando — sin píxeles válidos")
        return

    captura, created = CapturaSatelite.objects.update_or_create(
        campo=campo,
        area_campo=None,
        fecha=fecha_imagen_real,
        fuente="sentinel2",
        defaults=dict(
            ciclo=ciclo,
            nubosidad_pct=nubosidad,
            estado="procesada",
            fecha_procesado=timezone.now(),
        ),
    )

    indice, _ = IndiceVegetacion.objects.update_or_create(
        captura=captura,
        tipo="ndvi",
        defaults=dict(
            promedio=promedio,
            minimo=ndvi_min,
            maximo=ndvi_max,
        ),
    )

    if png_bytes:
        indice.imagen_png.save(
            f"ndvi_{campo.id}_{fecha_imagen_real}.png",
            ContentFile(png_bytes, name=f"ndvi_{campo.id}_{fecha_imagen_real}.png"),
            save=True,
        )

    accion = "Creada" if created else "Actualizada"
    stdout.write(
        f"  {accion} — NDVI avg={promedio:.3f} min={ndvi_min:.3f} "
        f"max={ndvi_max:.3f} nubes={nubosidad}%"
    )
