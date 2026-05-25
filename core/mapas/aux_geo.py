import json
import logging


logger = logging.getLogger(__name__)


def geojson_union_areas(campo) -> str | None:
    """
    Retorna un GeoJSON FeatureCollection (string) con TODAS
    las AreaCampo del campo que tengan contorno.

    Es la geometría que recibe Sentinel: una sola FeatureCollection
    que _bbox_from_geojson y _mascara_poligono saben manejar.

    Retorna None si el campo no tiene áreas con contorno.
    """
    from gestion_agro.models import AreaCampo

    areas = (
        AreaCampo.objects
        .filter(campo=campo, contorno__isnull=False)
        .exclude(contorno="")
        .order_by("-creado")
    )

    if not areas.exists():
        return None

    features = []
    for area in areas:
        try:
            gj = json.loads(area.contorno)
            if gj.get("type") == "FeatureCollection":
                features.extend(gj.get("features", []))
            elif gj.get("type") == "Feature":
                features.append(gj)
            else:
                features.append({
                    "type":       "Feature",
                    "geometry":   gj,
                    "properties": {"id": area.pk, "nombre": area.nombre},
                })
        except (json.JSONDecodeError, TypeError):
            logger.warning("AreaCampo id=%s contorno inválido", area.pk)

    if not features:
        return None

    return json.dumps({"type": "FeatureCollection", "features": features})


def extraer_bbox(geojson_str: str) -> list | None:
    """
    Extrae bounding box de cualquier GeoJSON (sin depender de sentinelhub).
    Retorna [min_lat, min_lng, max_lat, max_lng] o None.
    """
    if not geojson_str:
        return None
    try:
        gj = json.loads(geojson_str)
        coords = []

        def _extraer(geom):
            if not geom:
                return
            t = geom.get("type", "")
            if t == "FeatureCollection":
                for f in geom.get("features", []):
                    _extraer(f.get("geometry"))
            elif t == "Feature":
                _extraer(geom.get("geometry"))
            elif t == "Polygon":
                coords.extend(geom["coordinates"][0])
            elif t == "MultiPolygon":
                for poly in geom["coordinates"]:
                    coords.extend(poly[0])

        _extraer(gj)

        if not coords:
            return None

        lngs = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return [min(lats), min(lngs), max(lats), max(lngs)]

    except (json.JSONDecodeError, TypeError, KeyError):
        return None