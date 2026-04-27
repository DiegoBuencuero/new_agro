"""
Conversión de shapefile a GeoJSON minificado.
Se ejecuta UNA SOLA VEZ al subir el archivo.
Dependencia: pip install pyshp
"""
import json
import os
import tempfile

import shapefile  # pyshp


def procesar_shapefile_a_geojson(archivos_dict, variable_name="rate"):
    """
    archivos_dict: {"shp": <UploadedFile>, "shx": <UploadedFile>, "dbf": <UploadedFile>}
    Devuelve: (geojson_str_minificado, stats_dict)
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "data")
        for ext, f in archivos_dict.items():
            path = base + "." + ext
            with open(path, "wb") as out:
                for chunk in f.chunks():
                    out.write(chunk)

        sf = shapefile.Reader(base)

        features = []
        valores = []
        min_lng, min_lat = float("inf"), float("inf")
        max_lng, max_lat = float("-inf"), float("-inf")

        for shape_rec in sf.iterShapeRecords():
            shp = shape_rec.shape
            rec = shape_rec.record.as_dict()

            # Buscar variable (case-insensitive). Si no la encuentra, primer numérico.
            valor = None
            for k, v in rec.items():
                if k.lower() == variable_name.lower():
                    valor = v
                    break
            if valor is None:
                for v in rec.values():
                    if isinstance(v, (int, float)):
                        valor = v
                        break

            if isinstance(valor, (int, float)):
                valores.append(float(valor))

            geom = _shape_a_geojson(shp)
            if geom is None:
                continue

            if shp.bbox:
                bx1, by1, bx2, by2 = shp.bbox
                if bx1 < min_lng: min_lng = bx1
                if by1 < min_lat: min_lat = by1
                if bx2 > max_lng: max_lng = bx2
                if by2 > max_lat: max_lat = by2

            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "v": valor,  # nombre corto a propósito = JSON más liviano
                    **rec,
                },
            })

        geojson = {"type": "FeatureCollection", "features": features}
        geojson_str = json.dumps(geojson, separators=(",", ":"), default=str)

        stats = {
            "num_features": len(features),
            "valor_min": min(valores) if valores else None,
            "valor_max": max(valores) if valores else None,
            "valor_promedio": sum(valores) / len(valores) if valores else None,
            "bbox_min_lng": min_lng if min_lng != float("inf") else None,
            "bbox_min_lat": min_lat if min_lat != float("inf") else None,
            "bbox_max_lng": max_lng if max_lng != float("-inf") else None,
            "bbox_max_lat": max_lat if max_lat != float("-inf") else None,
        }

        return geojson_str, stats


def _shape_a_geojson(shp):
    """Convierte shape de pyshp a GeoJSON (Polygon/Point/LineString)."""
    if shp.shapeTypeName == "POLYGON":
        parts = list(shp.parts) + [len(shp.points)]
        rings = []
        for i in range(len(parts) - 1):
            ring = [[round(p[0], 6), round(p[1], 6)] for p in shp.points[parts[i]:parts[i + 1]]]
            rings.append(ring)
        return {"type": "Polygon", "coordinates": rings}

    elif shp.shapeTypeName == "POINT":
        p = shp.points[0]
        return {"type": "Point", "coordinates": [round(p[0], 6), round(p[1], 6)]}

    elif shp.shapeTypeName == "POLYLINE":
        return {
            "type": "LineString",
            "coordinates": [[round(p[0], 6), round(p[1], 6)] for p in shp.points],
        }

    return None
