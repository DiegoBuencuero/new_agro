"""
Conversión de shapefile a GeoJSON minificado.
Se ejecuta UNA SOLA VEZ al subir el archivo.
"""
import json
import os
import tempfile
import shapefile


def procesar_shapefile_a_geojson(archivos_subidos, nombre_variable="rate"):
    """
    archivos_subidos:
    {
        "shp": archivo_shp,
        "shx": archivo_shx,
        "dbf": archivo_dbf
    }

    Devuelve:
    (
        geojson_string,
        estadisticas
    )
    """

    # Crear carpeta temporal (se borra sola al terminar)
    with tempfile.TemporaryDirectory() as carpeta_temporal:

        # Ruta base: /tmp/xxxx/data
        ruta_base = os.path.join(carpeta_temporal, "data")

        # Guardar archivos subidos dentro de la carpeta temporal
        for extension in archivos_subidos:
            archivo = archivos_subidos[extension]

            ruta_archivo = f"{ruta_base}.{extension}"

            with open(ruta_archivo, "wb") as archivo_temporal:
                for bloque in archivo.chunks():
                    archivo_temporal.write(bloque)

        # Leer shapefile
        lector_shape = shapefile.Reader(ruta_base)

        lista_features = []
        lista_valores = []

        longitud_min = float("inf")
        latitud_min = float("inf")
        longitud_max = float("-inf")
        latitud_max = float("-inf")

        # Recorrer cada geometría del shapefile
        for registro in lector_shape.iterShapeRecords():

            geometria_shape = registro.shape
            atributos = registro.record.as_dict()

            # Buscar el valor de la variable
            valor_variable = None

            # Primero intenta encontrar el campo por nombre
            for nombre_campo, valor_campo in atributos.items():
                if nombre_campo.lower() == nombre_variable.lower():
                    valor_variable = valor_campo
                    break

            # Si no encuentra ese campo, usar el primer valor numérico
            if valor_variable is None:
                for valor_campo in atributos.values():
                    if isinstance(valor_campo, (int, float)):
                        valor_variable = valor_campo
                        break

            # Guardar para estadísticas
            if isinstance(valor_variable, (int, float)):
                lista_valores.append(float(valor_variable))

            # Convertir geometría a GeoJSON
            geometria_geojson = convertir_shape_a_geojson(geometria_shape)

            if geometria_geojson is None:
                continue

            # Calcular límites del mapa (bounding box)
            if geometria_shape.bbox:
                min_x, min_y, max_x, max_y = geometria_shape.bbox

                if min_x < longitud_min:
                    longitud_min = min_x

                if min_y < latitud_min:
                    latitud_min = min_y

                if max_x > longitud_max:
                    longitud_max = max_x

                if max_y > latitud_max:
                    latitud_max = max_y

            # Crear propiedades
            propiedades = atributos.copy()
            propiedades["v"] = valor_variable

            # Crear feature GeoJSON
            feature = {
                "type": "Feature",
                "geometry": geometria_geojson,
                "properties": propiedades,
            }

            lista_features.append(feature)

        # Crear GeoJSON final
        geojson = {
            "type": "FeatureCollection",
            "features": lista_features,
        }

        geojson_string = json.dumps(
            geojson,
            separators=(",", ":"),
            default=str
        )

        # Calcular estadísticas
        estadisticas = {
            "num_features": len(lista_features),

            "valor_min":
                min(lista_valores)
                if lista_valores else None,

            "valor_max":
                max(lista_valores)
                if lista_valores else None,

            "valor_promedio":
                sum(lista_valores) / len(lista_valores)
                if lista_valores else None,

            "bbox_min_lng":
                longitud_min
                if longitud_min != float("inf")
                else None,

            "bbox_min_lat":
                latitud_min
                if latitud_min != float("inf")
                else None,

            "bbox_max_lng":
                longitud_max
                if longitud_max != float("-inf")
                else None,

            "bbox_max_lat":
                latitud_max
                if latitud_max != float("-inf")
                else None,
        }

        return geojson_string, estadisticas


def procesar_kml_a_geojson(archivo):
    """
    Recibe archivo .kml o .kmz
    Devuelve:
    (
        geojson_string,
        estadisticas
    )
    """

    import io
    import zipfile
    import xml.etree.ElementTree as ET

    contenido_archivo = archivo.read()

    # Detectar extensión
    extension = archivo.name.rsplit(".", 1)[-1].lower()

    # Si es KMZ, abrir ZIP y sacar el KML interno
    if extension == "kmz":
        with zipfile.ZipFile(io.BytesIO(contenido_archivo)) as archivo_zip:

            nombre_kml = None

            for nombre in archivo_zip.namelist():
                if nombre.lower().endswith(".kml"):
                    nombre_kml = nombre
                    break

            if not nombre_kml:
                raise ValueError(
                    "El archivo KMZ no contiene ningún archivo KML"
                )

            contenido_archivo = archivo_zip.read(nombre_kml)

    # Quitar BOM si existe
    if contenido_archivo.startswith(b'\xef\xbb\xbf'):
        contenido_archivo = contenido_archivo[3:]

    # Leer XML
    raiz_xml = ET.fromstring(contenido_archivo)

    # Detectar namespace
    namespace = ""

    if raiz_xml.tag.startswith("{"):
        namespace = raiz_xml.tag.split("}")[0][1:]

    def crear_tag(nombre):
        if namespace:
            return f"{{{namespace}}}{nombre}"
        return nombre

    def buscar_todos(nodo, nombre):
        return nodo.findall(f".//{crear_tag(nombre)}")

    def convertir_coordenadas(texto):

        puntos = []

        texto = texto.strip().replace("\n", " ")

        for parte in texto.split():

            datos = parte.split(",")

            try:
                longitud = round(float(datos[0]), 6)
                latitud = round(float(datos[1]), 6)

                puntos.append([longitud, latitud])

            except:
                continue

        return puntos

    lista_features = []

    longitud_min = float("inf")
    latitud_min = float("inf")
    longitud_max = float("-inf")
    latitud_max = float("-inf")

    # Buscar polígonos
    for poligono in buscar_todos(raiz_xml, "Polygon"):

        coordenadas = poligono.find(
            f".//{crear_tag('coordinates')}"
        )

        if coordenadas is None:
            continue

        if not coordenadas.text:
            continue

        puntos = convertir_coordenadas(
            coordenadas.text
        )

        if len(puntos) < 3:
            continue

        # Actualizar límites
        for longitud, latitud in puntos:

            if longitud < longitud_min:
                longitud_min = longitud

            if latitud < latitud_min:
                latitud_min = latitud

            if longitud > longitud_max:
                longitud_max = longitud

            if latitud > latitud_max:
                latitud_max = latitud

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [puntos],
            },
            "properties": {},
        }

        lista_features.append(feature)

    if not lista_features:
        raise ValueError(
            "No se encontraron polígonos en el archivo"
        )

    geojson = {
        "type": "FeatureCollection",
        "features": lista_features,
    }

    geojson_string = json.dumps(
        geojson,
        separators=(",", ":")
    )

    estadisticas = {
        "num_features": len(lista_features),
        "bbox_min_lng": longitud_min,
        "bbox_min_lat": latitud_min,
        "bbox_max_lng": longitud_max,
        "bbox_max_lat": latitud_max,
    }

    return geojson_string, estadisticas


def convertir_shape_a_geojson(geometria_shape):
    """
    Convierte shape a formato GeoJSON
    """

    if geometria_shape.shapeTypeName == "POLYGON":

        indices_partes = list(
            geometria_shape.parts
        )

        indices_partes.append(
            len(geometria_shape.points)
        )

        lista_rings = []

        for i in range(
            len(indices_partes) - 1
        ):

            inicio = indices_partes[i]
            fin = indices_partes[i + 1]

            puntos = []

            for punto in geometria_shape.points[inicio:fin]:

                longitud = round(punto[0], 6)
                latitud = round(punto[1], 6)

                puntos.append(
                    [longitud, latitud]
                )

            lista_rings.append(puntos)

        return {
            "type": "Polygon",
            "coordinates": lista_rings,
        }

    elif geometria_shape.shapeTypeName == "POINT":

        punto = geometria_shape.points[0]

        return {
            "type": "Point",
            "coordinates": [
                round(punto[0], 6),
                round(punto[1], 6),
            ],
        }

    elif geometria_shape.shapeTypeName == "POLYLINE":

        puntos = []

        for punto in geometria_shape.points:

            longitud = round(punto[0], 6)
            latitud = round(punto[1], 6)

            puntos.append(
                [longitud, latitud]
            )

        return {
            "type": "LineString",
            "coordinates": puntos,
        }

    return None





# import json
# import os
# import tempfile

# import shapefile  # pyshp


# def procesar_shapefile_a_geojson(archivos_dict, variable_name="rate"):
#     """
#     archivos_dict: {"shp": <UploadedFile>, "shx": <UploadedFile>, "dbf": <UploadedFile>}
#     Devuelve: (geojson_str_minificado, stats_dict)
#     """
#     with tempfile.TemporaryDirectory() as tmp: # se crea carpeta temporal y despues se borra sola , por eso usamo s with
#         base = os.path.join(tmp, "data")
#         for ext, f in archivos_dict.items():
#             path = base + "." + ext
#             with open(path, "wb") as out:
#                 for chunk in f.chunks():
#                     out.write(chunk)

#         sf = shapefile.Reader(base)

#         features = []
#         valores = []
#         min_lng, min_lat = float("inf"), float("inf")
#         max_lng, max_lat = float("-inf"), float("-inf")

#         for shape_rec in sf.iterShapeRecords():
#             shp = shape_rec.shape
#             rec = shape_rec.record.as_dict()

#             # Buscar variable (case-insensitive). Si no la encuentra, primer numérico.
#             valor = None
#             for k, v in rec.items():
#                 if k.lower() == variable_name.lower():
#                     valor = v
#                     break
#             if valor is None:
#                 for v in rec.values():
#                     if isinstance(v, (int, float)):
#                         valor = v
#                         break

#             if isinstance(valor, (int, float)):
#                 valores.append(float(valor))

#             geom = _shape_a_geojson(shp)
#             if geom is None:
#                 continue

#             if shp.bbox:
#                 bx1, by1, bx2, by2 = shp.bbox
#                 if bx1 < min_lng: min_lng = bx1
#                 if by1 < min_lat: min_lat = by1
#                 if bx2 > max_lng: max_lng = bx2
#                 if by2 > max_lat: max_lat = by2

#             features.append({
#                 "type": "Feature",
#                 "geometry": geom,
#                 "properties": {
#                     "v": valor,  # nombre corto a propósito = JSON más liviano
#                     **rec,
#                 },
#             })

#         geojson = {"type": "FeatureCollection", "features": features}
#         geojson_str = json.dumps(geojson, separators=(",", ":"), default=str)

#         stats = {
#             "num_features": len(features),
#             "valor_min": min(valores) if valores else None,
#             "valor_max": max(valores) if valores else None,
#             "valor_promedio": sum(valores) / len(valores) if valores else None,
#             "bbox_min_lng": min_lng if min_lng != float("inf") else None,
#             "bbox_min_lat": min_lat if min_lat != float("inf") else None,
#             "bbox_max_lng": max_lng if max_lng != float("-inf") else None,
#             "bbox_max_lat": max_lat if max_lat != float("-inf") else None,
#         }

#         return geojson_str, stats


# def procesar_kml_a_geojson(archivo):
#     """
#     archivo: UploadedFile (.kml o .kmz)
#     Devuelve: (geojson_str, stats_dict)
#     """
#     import io
#     import zipfile
#     import xml.etree.ElementTree as ET

#     data = archivo.read()

#     # KMZ = ZIP con doc.kml adentro
#     ext = archivo.name.rsplit('.', 1)[-1].lower() if '.' in archivo.name else ''
#     if ext == 'kmz':
#         with zipfile.ZipFile(io.BytesIO(data)) as z:
#             kml_name = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
#             if not kml_name:
#                 raise ValueError("El archivo KMZ no contiene ningún .kml")
#             data = z.read(kml_name)

#     # Quitar BOM si existe
#     if data.startswith(b'\xef\xbb\xbf'):
#         data = data[3:]

#     root = ET.fromstring(data)

#     # Detectar namespace automáticamente
#     ns_uri = ""
#     if root.tag.startswith("{"):
#         ns_uri = root.tag.split("}")[0][1:]

#     def _tag(name):
#         return f"{{{ns_uri}}}{name}" if ns_uri else name

#     def _find_all(node, name):
#         return node.findall(f".//{_tag(name)}")

#     def _parse_coords(text):
#         ring = []
#         for token in text.strip().replace("\n", " ").split():
#             token = token.strip()
#             if not token:
#                 continue
#             parts = token.split(",")
#             try:
#                 lng, lat = round(float(parts[0]), 6), round(float(parts[1]), 6)
#                 ring.append([lng, lat])
#             except (ValueError, IndexError):
#                 continue
#         return ring

#     features = []
#     min_lng, min_lat = float("inf"),  float("inf")
#     max_lng, max_lat = float("-inf"), float("-inf")

#     for polygon in _find_all(root, "Polygon"):
#         # Outer boundary
#         outer = polygon.find(f".//{_tag('outerBoundaryIs')}")
#         coords_el = (outer.find(f".//{_tag('coordinates')}") if outer is not None else None) \
#                     or polygon.find(f".//{_tag('coordinates')}")
#         if coords_el is None or not coords_el.text:
#             continue

#         ring = _parse_coords(coords_el.text)
#         if len(ring) < 3:
#             continue

#         for lng, lat in ring:
#             if lng < min_lng: min_lng = lng
#             if lat < min_lat: min_lat = lat
#             if lng > max_lng: max_lng = lng
#             if lat > max_lat: max_lat = lat

#         features.append({
#             "type": "Feature",
#             "geometry": {"type": "Polygon", "coordinates": [ring]},
#             "properties": {},
#         })

#     if not features:
#         # Intentar extraer cualquier coordenada como fallback
#         for coords_el in _find_all(root, "coordinates"):
#             if not coords_el.text:
#                 continue
#             ring = _parse_coords(coords_el.text)
#             if len(ring) < 3:
#                 continue
#             for lng, lat in ring:
#                 if lng < min_lng: min_lng = lng
#                 if lat < min_lat: min_lat = lat
#                 if lng > max_lng: max_lng = lng
#                 if lat > max_lat: max_lat = lat
#             features.append({
#                 "type": "Feature",
#                 "geometry": {"type": "Polygon", "coordinates": [ring]},
#                 "properties": {},
#             })

#     if not features:
#         raise ValueError(f"No se encontraron polígonos en el KML/KMZ (namespace: '{ns_uri}')")

#     geojson = {"type": "FeatureCollection", "features": features}
#     geojson_str = json.dumps(geojson, separators=(",", ":"))
#     stats = {
#         "num_features":   len(features),
#         "bbox_min_lng":   min_lng if min_lng != float("inf") else None,
#         "bbox_min_lat":   min_lat if min_lat != float("inf") else None,
#         "bbox_max_lng":   max_lng if max_lng != float("-inf") else None,
#         "bbox_max_lat":   max_lat if max_lat != float("-inf") else None,
#     }
#     return geojson_str, stats


# def _shape_a_geojson(shp):
#     """Convierte shape de pyshp a GeoJSON (Polygon/Point/LineString)."""
#     if shp.shapeTypeName == "POLYGON":
#         parts = list(shp.parts) + [len(shp.points)]
#         rings = []
#         for i in range(len(parts) - 1):
#             ring = [[round(p[0], 6), round(p[1], 6)] for p in shp.points[parts[i]:parts[i + 1]]]
#             rings.append(ring)
#         return {"type": "Polygon", "coordinates": rings}

#     elif shp.shapeTypeName == "POINT":
#         p = shp.points[0]
#         return {"type": "Point", "coordinates": [round(p[0], 6), round(p[1], 6)]}

#     elif shp.shapeTypeName == "POLYLINE":
#         return {
#             "type": "LineString",
#             "coordinates": [[round(p[0], 6), round(p[1], 6)] for p in shp.points],
#         }

#     return None
