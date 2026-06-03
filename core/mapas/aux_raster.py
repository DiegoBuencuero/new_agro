import io
import json

import numpy as np


# Columnas geométricas/administrativas que NO son variables de análisis
_COLS_IGNORAR = {
    "area", "perimeter", "fid", "id", "objectid", "shape_area", "shape_leng",
    "shape_length", "gid", "oid", "geom",
}


def calcular_bbox(features):
    """[min_lng, min_lat, max_lng, max_lat] desde una lista de features GeoJSON."""
    lngs, lats = [], []
    for f in features:
        geom  = f.get("geometry", {})
        gtype = geom.get("type")
        if gtype == "Polygon":
            for ring in geom.get("coordinates", []):
                for pt in ring:
                    lngs.append(pt[0]); lats.append(pt[1])
        elif gtype == "Point":
            pt = geom.get("coordinates", [])
            if pt:
                lngs.append(pt[0]); lats.append(pt[1])
    if not lngs:
        return None
    return [min(lngs), min(lats), max(lngs), max(lats)]


def _detectar_columna(features, columna_preferida="v"):
    """
    Devuelve la columna numérica a usar para colorizar.
    1. Si 'columna_preferida' existe y tiene valores numéricos → úsala.
    2. Si no, busca la primera columna numérica que no sea administrativa.
    3. Si hay varias candidatas, elige la de mayor varianza (la más informativa).
    """
    if not features:
        return columna_preferida

    props0 = features[0].get("properties") or {}

    # Candidato 1: columna preferida
    if isinstance(props0.get(columna_preferida), (int, float)):
        return columna_preferida

    # Candidato 2: primera columna numérica no administrativa
    candidatas = []
    for k, v in props0.items():
        if k.lower() in _COLS_IGNORAR:
            continue
        if isinstance(v, (int, float)):
            candidatas.append(k)

    if not candidatas:
        return columna_preferida  # sin columna numérica útil

    if len(candidatas) == 1:
        return candidatas[0]

    # Elegir la de mayor varianza
    mejor, mejor_var = candidatas[0], 0.0
    for k in candidatas:
        vals = [f["properties"][k] for f in features
                if isinstance((f.get("properties") or {}).get(k), (int, float))]
        if len(vals) > 1:
            var = float(np.var(vals))
            if var > mejor_var:
                mejor_var = var
                mejor = k
    return mejor


PALETA_SUELO = [
    "#990000",  # 1 — muy bajo
    "#cc0000",  # 2
    "#ff3300",  # 3
    "#ff6600",  # 4
    "#ff9900",  # 5
    "#ffcc00",  # 6 — medio
    "#ccff00",  # 7
    "#99ff00",  # 8
    "#66cc00",  # 9
    "#339900",  # 10 — muy alto
]


# ─────────────────────────────────────────────
# 1. Asignar colores por bins (10 clases)
# ─────────────────────────────────────────────

def colorear_geojson(geojson_dict, columna="v"):
    """
    Recibe FeatureCollection con properties[columna] numérico.
    Auto-detecta la columna si 'columna' no existe en los datos.
    Agrega properties.color a cada feature.
    Retorna (geojson_dict_modificado, leyenda, estadisticas).
    """
    features = geojson_dict.get("features", [])

    # Auto-detección de columna
    columna = _detectar_columna(features, columna_preferida=columna)

    vals = [
        float(f["properties"][columna])
        for f in features
        if isinstance((f.get("properties") or {}).get(columna), (int, float))
    ]

    if not vals:
        for f in features:
            (f.setdefault("properties", {}))["color"] = "#aaaaaa"
        return geojson_dict, [], {}

    arr  = np.array(vals)
    vmin = float(arr.min())
    vmax = float(arr.max())

    if vmin == vmax:
        for f in features:
            (f.setdefault("properties", {}))["color"] = PALETA_SUELO[4]
        leyenda = [{"rango": str(round(vmin, 2)), "color": PALETA_SUELO[4], "columna": columna}]
        stats   = {"min": round(vmin, 2), "max": round(vmax, 2), "prom": round(vmin, 2),
                   "std": 0, "columna": columna}
        return geojson_dict, leyenda, stats

    bins = np.linspace(vmin, vmax, 11)

    for f in features:
        v = (f.get("properties") or {}).get(columna)
        if isinstance(v, (int, float)):
            idx = int(np.digitize(float(v), bins)) - 1
            idx = max(0, min(9, idx))
            f["properties"]["color"] = PALETA_SUELO[idx]
        else:
            f["properties"]["color"] = "#aaaaaa"

    etiquetas = [f"{bins[i]:.2f} – {bins[i+1]:.2f}" for i in range(10)]
    leyenda   = [{"rango": e, "color": c} for e, c in zip(etiquetas, PALETA_SUELO)]
    stats     = {
        "min":     round(float(arr.min()),  2),
        "max":     round(float(arr.max()),  2),
        "prom":    round(float(arr.mean()), 2),
        "std":     round(float(arr.std()),  2),
        "columna": columna,
    }
    return geojson_dict, leyenda, stats


# ─────────────────────────────────────────────
# 2. Rasterizar a PNG (matplotlib, sin axes)
# ─────────────────────────────────────────────

def rasterizar_a_png(geojson_dict, bbox):
    """
    geojson_dict: FeatureCollection con properties.color en cada feature.
    bbox: [min_lng, min_lat, max_lng, max_lat]
    Retorna bytes PNG (RGBA transparente donde no hay datos).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPolygon
    from matplotlib.collections import PatchCollection

    min_lng, min_lat, max_lng, max_lat = bbox

    # Asegurar bbox válida
    if min_lng >= max_lng or min_lat >= max_lat:
        raise ValueError(f"Bbox inválida: {bbox}")

    w_deg = max_lng - min_lng
    h_deg = max_lat - min_lat

    PX_PER_DEG = 10_000
    width_px  = max(128, min(2048, int(w_deg * PX_PER_DEG)))
    height_px = max(64,  min(1024, int(h_deg * PX_PER_DEG)))

    dpi   = 96
    fig_w = width_px  / dpi
    fig_h = height_px / dpi

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.set_xlim(min_lng, max_lng)
    ax.set_ylim(min_lat, max_lat)
    ax.set_aspect("auto")
    ax.axis("off")

    patches = []
    colors  = []
    point_patches = []
    point_colors  = []

    pt_side = w_deg / width_px * 4

    for feature in geojson_dict.get("features", []):
        geom  = feature.get("geometry") or {}
        color = (feature.get("properties") or {}).get("color", "#aaaaaa")
        gtype = geom.get("type")

        if gtype == "Polygon":
            ring = (geom.get("coordinates") or [[]])[0]
            if ring and len(ring) >= 3:
                try:
                    pts = np.array([[float(p[0]), float(p[1])] for p in ring])
                    patches.append(MplPolygon(pts, closed=True))
                    colors.append(color)
                except Exception:
                    pass

        elif gtype == "MultiPolygon":
            for poly in (geom.get("coordinates") or []):
                ring = poly[0] if poly else []
                if ring and len(ring) >= 3:
                    try:
                        pts = np.array([[float(p[0]), float(p[1])] for p in ring])
                        patches.append(MplPolygon(pts, closed=True))
                        colors.append(color)
                    except Exception:
                        pass

        elif gtype == "Point":
            try:
                x, y = float(geom["coordinates"][0]), float(geom["coordinates"][1])
                pts  = [[x - pt_side, y - pt_side], [x + pt_side, y - pt_side],
                        [x + pt_side, y + pt_side], [x - pt_side, y + pt_side]]
                point_patches.append(MplPolygon(pts, closed=True))
                point_colors.append(color)
            except Exception:
                pass

    if patches:
        ax.add_collection(
            PatchCollection(patches, facecolors=colors, edgecolors="none", linewidths=0)
        )
    if point_patches:
        ax.add_collection(
            PatchCollection(point_patches, facecolors=point_colors, edgecolors="none", linewidths=0)
        )

    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True,
                bbox_inches="tight", pad_inches=0, dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────
# 3. Point-in-polygon para el click
# ─────────────────────────────────────────────

def _ray_cast(px, py, ring):
    n      = len(ring)
    inside = False
    j      = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def buscar_feature_en_punto(geojson_dict, lng, lat, radio_grados=None):
    """
    Retorna las properties del feature más cercano a (lng, lat), o None.
    Para Polygon/MultiPolygon verifica contención exacta.
    Para Point devuelve siempre el más cercano (sin restricción de radio).
    """
    mejor_props = None
    mejor_dist  = float("inf")

    for feature in geojson_dict.get("features", []):
        geom  = feature.get("geometry") or {}
        gtype = geom.get("type")
        props = feature.get("properties") or {}

        if gtype == "Polygon":
            ring = (geom.get("coordinates") or [[]])[0]
            if ring and _ray_cast(lng, lat, ring):
                return props

        elif gtype == "MultiPolygon":
            for poly in (geom.get("coordinates") or []):
                ring = poly[0] if poly else []
                if ring and _ray_cast(lng, lat, ring):
                    return props

        elif gtype == "Point":
            x, y = geom["coordinates"][0], geom["coordinates"][1]
            dist = (x - lng) ** 2 + (y - lat) ** 2
            if dist < mejor_dist:
                mejor_dist  = dist
                mejor_props = props

    return mejor_props  # siempre devuelve el más cercano para puntos
