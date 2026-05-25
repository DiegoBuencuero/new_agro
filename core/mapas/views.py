import json
import threading
import zipfile
import io as _io

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from agro.models import Empresa
from gestion_agro.models import Campo, AreaCampo
from mapas.models import CapturaSatelite, IndiceVegetacion, ArchivoAnalitico, MedicionCampo
from mapas.forms import CapaMapaForm
from mapas.aux_shapefile import procesar_shapefile_a_geojson, procesar_kml_a_geojson
from mapas.aux_geo import geojson_union_areas, extraer_bbox
from mapas.aux_sentenial import _get_sh_config, procesar_campo
from mapas.aux_raster import colorear_geojson, rasterizar_a_png, buscar_feature_en_punto, calcular_bbox


# =====================================================
# VISTAS PRINCIPALES
# =====================================================

@login_required
def vista_mapas(request):
    empresa   = request.user.profile.empresa
    campos    = Campo.objects.filter(empresa=empresa).order_by("nombre")
    areas     = AreaCampo.objects.filter(campo__empresa=empresa).order_by("campo__nombre", "nombre")
    campo_sel = None
    capturas_ndvi = []

    campo_id = request.GET.get("campo")
    if campo_id:
        campo_sel = campos.filter(id=campo_id).first()
        if campo_sel:
            capturas_ndvi = (
                CapturaSatelite.objects
                .filter(campo=campo_sel)
                .prefetch_related("indices")
                .order_by("-fecha")
            )

    return render(request, "temp_mapas/vista_mapas.html", {
        "campos":             campos,
        "areas":              areas,
        "campo_sel":          campo_sel,
        "capturas_ndvi":      capturas_ndvi,
        "mediciones_suelo":   [],
        "mediciones_cosecha": [],
        "comp_filas":         [],
        "comp_fechas":        [],
    })


@login_required
def vista_ndvi(request):
    empresa = request.user.profile.empresa
    campos  = Campo.objects.filter(empresa=empresa).order_by("nombre")
    leyenda = [
        ("rgb(200,50,50)",  "< 0.1 — Crítico"),
        ("rgb(230,140,30)", "0.1–0.3 — Estrés"),
        ("rgb(180,210,60)", "0.3–0.5 — Normal"),
        ("rgb(30,140,40)",  "≥ 0.5 — Óptimo"),
    ]
    return render(request, "temp_mapas/ndvi_campo.html", {
        "campos":       campos,
        "leyenda_ndvi": leyenda,
    })


# =====================================================
# AJAX — NDVI
# =====================================================

@login_required
@require_POST
def vista_ndvi_procesar(request, campo_id):
    """Dispara Sentinel para un campo y devuelve JSON."""
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)

    if not geojson_union_areas(campo) and not campo.contorno:
        return JsonResponse({"ok": False, "error": "El campo no tiene áreas ni contorno definido."}, status=400)

    try:
        config = _get_sh_config()
    except RuntimeError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    class Log:
        def __init__(self): self.lines = []
        def write(self, s): self.lines.append(str(s))

    log         = Log()
    fecha_hasta = date.today()
    forzar      = request.POST.get("forzar") == "1"

    ultima = (
        CapturaSatelite.objects
        .filter(campo=campo, fuente="sentinel2", estado="procesada")
        .order_by("-fecha")
        .first()
    )

    if forzar and ultima:
        indice = ultima.indices.filter(tipo="ndvi").first()
        if indice and indice.imagen_png:
            indice.imagen_png.delete(save=False)
        ultima.delete()
        ultima = None

    if ultima and not forzar:
        fecha_desde = ultima.fecha + timedelta(days=1)
        if fecha_desde > fecha_hasta:
            return JsonResponse({
                "ok": True, "sin_nuevas": True,
                "log": [f"La última captura es del {ultima.fecha}. No hay imágenes nuevas."],
            })
    else:
        fecha_desde = fecha_hasta - timedelta(days=5)

    try:
        procesar_campo(campo, fecha_desde, fecha_hasta, config, log)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e), "log": log.lines}, status=500)

    return JsonResponse({"ok": True, "log": log.lines})


@login_required
def ajax_ndvi_serie(request, campo_id):
    """Serie temporal NDVI de un campo — para Chart.js."""
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)

    capturas = (
        CapturaSatelite.objects
        .filter(campo=campo, fuente="sentinel2", estado="procesada")
        .prefetch_related("indices")
        .order_by("fecha")
    )

    data = []
    for c in capturas:
        indice = next((i for i in c.indices.all() if i.tipo == "ndvi"), None)
        data.append({
            "fecha":          str(c.fecha),
            "ndvi_promedio":  indice.promedio if indice else None,
            "ndvi_min":       indice.minimo   if indice else None,
            "ndvi_max":       indice.maximo   if indice else None,
            "nubosidad":      c.nubosidad_pct,
            "estado":         c.estado,
            "imagen_url":     indice.imagen_png.url if (indice and indice.imagen_png) else None,
        })

    geojson_str  = geojson_union_areas(campo) or campo.contorno
    bbox         = extraer_bbox(geojson_str)
    area_geojson = json.loads(geojson_str) if geojson_str else None

    return JsonResponse({
        "ok":           True,
        "campo":        {"id": campo.id, "nombre": campo.nombre},
        "tiene_area":   bool(geojson_str),
        "bbox":         bbox,
        "area_geojson": area_geojson,
        "capturas":     data,
    })


# =====================================================
# AJAX — ÁREAS DEL CAMPO
# =====================================================

@login_required
def ajax_areas_listar(request, campo_id):
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    return JsonResponse({
        "ok": True,
        "areas": [
            {
                "id":            a.id,
                "nombre":        a.nombre,
                "descripcion":   a.descripcion,
                "superficie_ha": float(a.superficie_ha) if a.superficie_ha else None,
                "geojson":       json.loads(a.contorno) if a.contorno else None,
            }
            for a in campo.areas.all()
        ],
    })


@login_required
@require_POST
def ajax_area_crear(request, campo_id):
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        return JsonResponse({"ok": False, "error": "Nombre requerido"}, status=400)
    area = AreaCampo.objects.create(
        campo=campo,
        nombre=nombre,
        descripcion=body.get("descripcion", ""),
    )
    return JsonResponse({"ok": True, "id": area.id, "nombre": area.nombre})


@login_required
@require_POST
def ajax_area_guardar_geojson(request, area_id):
    empresa = request.user.profile.empresa
    area    = get_object_or_404(AreaCampo, id=area_id, campo__empresa=empresa)
    try:
        body       = json.loads(request.body)
        geojson    = body.get("geojson")
        superficie = body.get("superficie_ha")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)
    if not geojson:
        return JsonResponse({"ok": False, "error": "GeoJSON vacío"}, status=400)
    area.contorno = json.dumps(geojson)
    if superficie:
        area.superficie_ha = superficie
    area.save()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def ajax_area_eliminar(request, area_id):
    empresa = request.user.profile.empresa
    area    = get_object_or_404(AreaCampo, id=area_id, campo__empresa=empresa)
    area.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def ajax_area_cargar_shapefile(request, campo_id):
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    archivos = {}
    for ext in ("shp", "shx", "dbf"):
        f = request.FILES.get(ext)
        if not f:
            return JsonResponse({"ok": False, "error": f"Falta archivo .{ext}"}, status=400)
        archivos[ext] = f
    nombre = (request.POST.get("nombre") or "").strip() or f"Área {campo.areas.count() + 1}"
    try:
        geojson_str, stats = procesar_shapefile_a_geojson(archivos, nombre_variable="area")
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Error procesando shapefile: {e}"}, status=400)
    area = AreaCampo.objects.create(
        campo=campo,
        nombre=nombre,
        contorno=geojson_str,
        superficie_ha=stats.get("superficie_ha"),
    )
    return JsonResponse({
        "ok":      True,
        "id":      area.id,
        "nombre":  area.nombre,
        "geojson": json.loads(geojson_str),
        "bbox": [
            stats.get("bbox_min_lng"), stats.get("bbox_min_lat"),
            stats.get("bbox_max_lng"), stats.get("bbox_max_lat"),
        ],
    })


@login_required
@require_POST
def ajax_area_cargar_kml(request, campo_id):
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    archivo = request.FILES.get("kml")
    if not archivo:
        return JsonResponse({"ok": False, "error": "Falta el archivo KML/KMZ"}, status=400)
    nombre = (request.POST.get("nombre") or "").strip() or f"Área {campo.areas.count() + 1}"
    try:
        geojson_str, stats = procesar_kml_a_geojson(archivo)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    area = AreaCampo.objects.create(
        campo=campo,
        nombre=nombre,
        contorno=geojson_str,
        superficie_ha=stats.get("superficie_ha"),
    )
    return JsonResponse({
        "ok":      True,
        "id":      area.id,
        "nombre":  area.nombre,
        "geojson": json.loads(geojson_str),
        "bbox": [
            stats.get("bbox_min_lng"), stats.get("bbox_min_lat"),
            stats.get("bbox_max_lng"), stats.get("bbox_max_lat"),
        ],
    })


# =====================================================
# AJAX — CONTORNO / BOUNDARY
# =====================================================

@login_required
def ajax_boundary(request, campo_id):
    empresa     = request.user.profile.empresa
    campo       = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    geojson_str = geojson_union_areas(campo)
    if not geojson_str:
        return JsonResponse({"ok": True, "geojson": None})
    return JsonResponse({"ok": True, "geojson": json.loads(geojson_str)})


@login_required
@require_POST
def ajax_contorno_parsear(request):
    """Recibe ZIP (shapefile), KML o KMZ y devuelve GeoJSON sin guardar nada."""
    archivo = request.FILES.get("archivo")
    if not archivo:
        return JsonResponse({"ok": False, "error": "No se recibió ningún archivo"}, status=400)
    nombre = archivo.name.lower()
    try:
        if nombre.endswith(".kml") or nombre.endswith(".kmz"):
            geojson_str, stats = procesar_kml_a_geojson(archivo)

        elif nombre.endswith(".zip"):
            contenido = archivo.read()
            with zipfile.ZipFile(_io.BytesIO(contenido)) as z:
                nombres_zip = z.namelist()
                shp_n = next((n for n in nombres_zip if n.lower().endswith(".shp")), None)
                shx_n = next((n for n in nombres_zip if n.lower().endswith(".shx")), None)
                dbf_n = next((n for n in nombres_zip if n.lower().endswith(".dbf")), None)
                prj_n = next((n for n in nombres_zip if n.lower().endswith(".prj")), None)
                if not all([shp_n, shx_n, dbf_n]):
                    return JsonResponse({"ok": False, "error": "El ZIP debe contener .shp, .shx y .dbf"}, status=400)

                def _buf(name):
                    data = z.read(name)
                    b = _io.BytesIO(data)
                    b.name = name
                    b.chunks = lambda: [data]
                    return b

                archivos = {"shp": _buf(shp_n), "shx": _buf(shx_n), "dbf": _buf(dbf_n)}
                geojson_str, stats = procesar_shapefile_a_geojson(archivos)

                if prj_n:
                    try:
                        from pyproj import CRS, Transformer
                        prj_text   = z.read(prj_n).decode("utf-8", errors="ignore")
                        crs_origen = CRS.from_wkt(prj_text)
                        crs_wgs84  = CRS.from_epsg(4326)
                        if not crs_origen.equals(crs_wgs84):
                            transformer = Transformer.from_crs(crs_origen, crs_wgs84, always_xy=True)
                            gj = json.loads(geojson_str)
                            for feature in gj.get("features", []):
                                geom = feature.get("geometry", {})
                                if geom.get("type") == "Polygon":
                                    geom["coordinates"] = [
                                        [list(transformer.transform(x, y)) for x, y in ring]
                                        for ring in geom["coordinates"]
                                    ]
                                elif geom.get("type") == "MultiPolygon":
                                    geom["coordinates"] = [
                                        [
                                            [list(transformer.transform(x, y)) for x, y in ring]
                                            for ring in poly
                                        ]
                                        for poly in geom["coordinates"]
                                    ]
                            geojson_str = json.dumps(gj)
                    except Exception:
                        pass
        else:
            return JsonResponse({"ok": False, "error": "Formato no soportado. Usá ZIP, KML o KMZ"}, status=400)

        return JsonResponse({"ok": True, "geojson": json.loads(geojson_str), "bbox": stats})

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


# =====================================================
# AJAX — CAPAS ANALÍTICAS
# =====================================================

# =====================================================
# AJAX — SUELO
# =====================================================

@login_required
def ajax_suelo_listar(request, campo_id):
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    mediciones = (
        MedicionCampo.objects
        .filter(campo=campo, variable__tipo="suelo")
        .select_related("variable", "area_campo")
        .order_by("-fecha")
    )
    return JsonResponse({
        "ok": True,
        "mediciones": [
            {
                "id":       m.id,
                "variable": m.variable.nombre,
                "unidad":   m.variable.unidad,
                "promedio": m.promedio,
                "minimo":   m.minimo,
                "maximo":   m.maximo,
                "fecha":    str(m.fecha),
                "area":     m.area_campo.nombre if m.area_campo else None,
            }
            for m in mediciones
        ],
    })


@login_required
@require_POST
def ajax_suelo_cargar(request, campo_id):
    print(f"\n>>> SUELO CARGAR campo_id={campo_id} FILES={list(request.FILES.keys())} POST-area={request.POST.get('area')}")
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    print(f"    campo={campo.nombre}")

    area_id = request.POST.get("area")
    area    = None
    if area_id:
        area = AreaCampo.objects.filter(id=area_id, campo=campo).first()
        print(f"    area={area}")

    geojson_str  = None
    stats        = {}

    # ── Modo shapefile suelto (.shp + .shx + .dbf) ──────────────────
    if request.FILES.get("shp"):
        print("    modo: 3 archivos sueltos")
        partes = {}
        for ext in ("shp", "shx", "dbf"):
            f = request.FILES.get(ext)
            if not f:
                print(f"    ERROR: falta .{ext}")
                return JsonResponse({"ok": False, "error": f"Falta el archivo .{ext}"}, status=400)
            partes[ext] = f
            print(f"    .{ext} = {f.name} ({f.size} bytes)")

        try:
            geojson_str, stats = procesar_shapefile_a_geojson(partes)
            print(f"    shapefile OK → {stats.get('num_features')} features  bbox={stats.get('bbox_min_lng')},{stats.get('bbox_min_lat')},{stats.get('bbox_max_lng')},{stats.get('bbox_max_lat')}")
        except Exception as e:
            print(f"    ERROR procesar_shapefile: {e}")
            return JsonResponse({"ok": False, "error": f"Error procesando shapefile: {e}"}, status=400)

        buf  = _io.BytesIO()
        base = partes["shp"].name.rsplit(".", 1)[0]
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for ext, f in partes.items():
                f.seek(0)
                zf.writestr(f"{base}.{ext}", f.read())
        buf.seek(0)
        archivo_final = ContentFile(buf.read(), name=f"{base}.zip")
        tipo_archivo  = "shapefile"

    # ── Modo archivo único (ZIP, GeoJSON, KML, CSV) ──────────────────
    else:
        archivo = request.FILES.get("archivo")
        if not archivo:
            print("    ERROR: no se recibió archivo")
            return JsonResponse({"ok": False, "error": "No se recibió ningún archivo"}, status=400)

        nombre = archivo.name.lower()
        print(f"    modo: archivo único → {archivo.name} ({archivo.size} bytes)")

        if nombre.endswith(".zip"):
            tipo_archivo = "shapefile"
            try:
                contenido = archivo.read()
                print(f"    ZIP leído ({len(contenido)} bytes)")
                with zipfile.ZipFile(_io.BytesIO(contenido)) as z:
                    nombres_zip = z.namelist()
                    print(f"    ZIP contenido: {nombres_zip}")
                    shp_n = next((n for n in nombres_zip if n.lower().endswith(".shp")), None)
                    shx_n = next((n for n in nombres_zip if n.lower().endswith(".shx")), None)
                    dbf_n = next((n for n in nombres_zip if n.lower().endswith(".dbf")), None)
                    print(f"    shp={shp_n}  shx={shx_n}  dbf={dbf_n}")
                    if not all([shp_n, shx_n, dbf_n]):
                        faltantes = [f".{e}" for e, n in [("shp", shp_n), ("shx", shx_n), ("dbf", dbf_n)] if not n]
                        print(f"    ERROR faltan: {faltantes}")
                        return JsonResponse({"ok": False, "error": f"El ZIP debe contener: {', '.join(faltantes)}"}, status=400)

                    def _buf(name):
                        data = z.read(name)
                        b = _io.BytesIO(data)
                        b.name = name
                        b.chunks = lambda: [data]
                        return b

                    geojson_str, stats = procesar_shapefile_a_geojson(
                        {"shp": _buf(shp_n), "shx": _buf(shx_n), "dbf": _buf(dbf_n)}
                    )
                    print(f"    ZIP shapefile OK → {stats.get('num_features')} features  bbox={stats.get('bbox_min_lng')},{stats.get('bbox_min_lat')},{stats.get('bbox_max_lng')},{stats.get('bbox_max_lat')}")
                archivo.seek(0)
            except zipfile.BadZipFile:
                print("    ERROR: ZIP dañado")
                return JsonResponse({"ok": False, "error": "El archivo ZIP está dañado"}, status=400)
            except Exception as e:
                print(f"    ERROR procesando ZIP: {e}")
                return JsonResponse({"ok": False, "error": f"Error procesando shapefile: {e}"}, status=400)

        elif nombre.endswith(".kml") or nombre.endswith(".kmz"):
            tipo_archivo = "geojson"
            try:
                geojson_str, stats = procesar_kml_a_geojson(archivo)
                archivo.seek(0)
            except Exception as e:
                return JsonResponse({"ok": False, "error": f"Error procesando KML: {e}"}, status=400)

        elif nombre.endswith(".geojson") or nombre.endswith(".json"):
            tipo_archivo = "geojson"
            try:
                geojson_str = archivo.read().decode("utf-8")
                archivo.seek(0)
            except Exception as e:
                return JsonResponse({"ok": False, "error": f"Error leyendo GeoJSON: {e}"}, status=400)

        elif nombre.endswith(".csv"):
            tipo_archivo = "csv"

        else:
            return JsonResponse({"ok": False, "error": "Formato no soportado. Usá ZIP, Shapefile, GeoJSON, KML o CSV"}, status=400)

        archivo_final = archivo

    # ── Rasterización PNG ───────────────────────────────────────────────
    bbox_list  = None
    leyenda    = []
    estadisticas = {}
    png_name   = None

    if geojson_str:
        bbox_list = [
            stats.get("bbox_min_lng"), stats.get("bbox_min_lat"),
            stats.get("bbox_max_lng"), stats.get("bbox_max_lat"),
        ]
        gj = json.loads(geojson_str)
        print(f"    rasterizando {len(gj.get('features',[]))} features...")
        try:
            gj, leyenda, estadisticas = colorear_geojson(gj)
            png_bytes = rasterizar_a_png(gj, bbox_list)
            base_name = archivo_final.name.rsplit(".", 1)[0] if hasattr(archivo_final, "name") else "suelo"
            png_name  = f"{base_name}.png"
            print(f"    PNG generado: {len(png_bytes)} bytes")
        except Exception as e:
            print(f"    ERROR rasterizando: {e}")
            png_bytes = None

    print(f"    guardando ArchivoAnalitico tipo={tipo_archivo} estado={'procesado' if geojson_str else 'pendiente'}")
    registro = ArchivoAnalitico.objects.create(
        campo=campo,
        area_campo=area,
        archivo=archivo_final,
        tipo_archivo=tipo_archivo,
        cargado_por=request.user,
        estado="procesado" if geojson_str else "pendiente",
        bbox=bbox_list,
        leyenda=leyenda or None,
        estadisticas=estadisticas or None,
    )

    if geojson_str and png_bytes and png_name:
        registro.imagen_png.save(png_name, ContentFile(png_bytes), save=True)

    print(f"    guardado id={registro.id} path={registro.archivo.name}")

    respuesta = {"ok": True, "id": registro.id, "msg": "Archivo procesado correctamente."}
    if geojson_str and registro.imagen_png:
        respuesta["imagen_url"]   = registro.imagen_png.url
        respuesta["bbox"]         = bbox_list
        respuesta["leyenda"]      = leyenda
        respuesta["estadisticas"] = estadisticas
        print(f"    imagen_url={respuesta['imagen_url']}  bbox={bbox_list}")
    else:
        print("    sin imagen (CSV o error de parseo/rasterización)")

    print(f"<<< SUELO CARGAR ok={respuesta['ok']}\n")
    return JsonResponse(respuesta)


@login_required
def ajax_suelo_archivos(request, campo_id):
    empresa  = request.user.profile.empresa
    campo    = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    archivos = (
        ArchivoAnalitico.objects
        .filter(campo=campo)
        .order_by("-fecha_carga")
    )
    return JsonResponse({
        "ok": True,
        "archivos": [
            {
                "id":           a.id,
                "nombre":       a.archivo.name.split("/")[-1],
                "tipo":         a.tipo_archivo,
                "estado":       a.estado,
                "fecha":        a.fecha_carga.strftime("%d/%m/%Y"),
                "imagen_url":   a.imagen_png.url if a.imagen_png else None,
                "bbox":         a.bbox,
                "leyenda":      a.leyenda,
                "estadisticas": a.estadisticas,
                "mapeable":     bool(a.imagen_png),
            }
            for a in archivos
        ],
    })


@login_required
def ajax_suelo_clic(request, archivo_id):
    """Recibe lat/lng, devuelve propiedades del feature que contiene el punto."""
    empresa  = request.user.profile.empresa
    registro = get_object_or_404(ArchivoAnalitico, id=archivo_id, campo__empresa=empresa)
    try:
        lng = float(request.GET.get("lng"))
        lat = float(request.GET.get("lat"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "lat/lng inválidos"}, status=400)

    try:
        if registro.tipo_archivo == "shapefile":
            contenido = registro.archivo.read()
            with zipfile.ZipFile(_io.BytesIO(contenido)) as z:
                nombres = z.namelist()
                shp_n   = next((n for n in nombres if n.lower().endswith(".shp")), None)
                shx_n   = next((n for n in nombres if n.lower().endswith(".shx")), None)
                dbf_n   = next((n for n in nombres if n.lower().endswith(".dbf")), None)
                if not all([shp_n, shx_n, dbf_n]):
                    return JsonResponse({"ok": False, "error": "ZIP incompleto"})

                def _buf(name):
                    data = z.read(name)
                    b = _io.BytesIO(data); b.name = name; b.chunks = lambda: [data]; return b

                geojson_str, _ = procesar_shapefile_a_geojson(
                    {"shp": _buf(shp_n), "shx": _buf(shx_n), "dbf": _buf(dbf_n)}
                )
        elif registro.tipo_archivo == "geojson":
            geojson_str = registro.archivo.read().decode("utf-8")
        else:
            return JsonResponse({"ok": False, "error": "Tipo no soportado para click"})

        gj   = json.loads(geojson_str)
        props = buscar_feature_en_punto(gj, lng, lat)
        if props is None:
            return JsonResponse({"ok": True, "encontrado": False})
        # Limpiar campos internos antes de devolver
        props_clean = {k: v for k, v in props.items() if k not in ("color",)}
        return JsonResponse({"ok": True, "encontrado": True, "propiedades": props_clean})

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────
# SUELO — regenerar PNG para archivos sin imagen (background)
# ─────────────────────────────────────────────────────────────────────

def _regenerar_png_bg(archivo_id):
    from django.db import connection
    print(f"\n>>> REGEN_PNG id={archivo_id}")
    try:
        a = ArchivoAnalitico.objects.get(id=archivo_id)
        a.estado = "pendiente"
        a.save(update_fields=["estado"])

        features, bbox = _leer_features_archivo(a)
        print(f"    features={len(features)}  bbox={bbox}")
        if not features:
            print("    ERROR: sin features")
            ArchivoAnalitico.objects.filter(id=archivo_id).update(estado="error")
            return

        if not bbox or any(v is None for v in bbox):
            bbox = calcular_bbox(features)
        if not bbox:
            print("    ERROR: no se pudo calcular bbox")
            ArchivoAnalitico.objects.filter(id=archivo_id).update(estado="error")
            return

        gj = {"type": "FeatureCollection", "features": features}
        gj_col, leyenda, estadisticas = colorear_geojson(gj)
        print(f"    colorizado OK  leyenda={len(leyenda)} items")
        png_bytes = rasterizar_a_png(gj_col, bbox)
        print(f"    PNG generado: {len(png_bytes)} bytes")

        a.refresh_from_db()
        a.imagen_png.save(f"suelo_{archivo_id}.png", ContentFile(png_bytes), save=False)
        a.bbox         = bbox
        a.leyenda      = leyenda
        a.estadisticas = estadisticas
        a.estado       = "procesado"
        a.save()
        print(f"<<< REGEN_PNG id={archivo_id} OK")
    except Exception as e:
        print(f"<<< REGEN_PNG id={archivo_id} ERROR: {e}")
        import traceback; traceback.print_exc()
        ArchivoAnalitico.objects.filter(id=archivo_id).update(estado="error")
    finally:
        connection.close()


@login_required
@require_POST
def ajax_suelo_regenerar(request, archivo_id):
    empresa  = request.user.profile.empresa
    registro = get_object_or_404(ArchivoAnalitico, id=archivo_id, campo__empresa=empresa)
    if registro.tipo_archivo not in ("shapefile", "geojson"):
        return JsonResponse({"ok": False, "error": "Tipo no soportado"}, status=400)
    threading.Thread(target=_regenerar_png_bg, args=(registro.id,), daemon=True).start()
    return JsonResponse({"ok": True})


# ─────────────────────────────────────────────────────────────────────
# SUELO — combinar N archivos (procesamiento asíncrono)
# ─────────────────────────────────────────────────────────────────────

def _leer_features_archivo(a):
    """Lee un ArchivoAnalitico y devuelve (features_list, bbox) o ([], None)."""
    try:
        if a.tipo_archivo == "shapefile":
            contenido = a.archivo.read()
            with zipfile.ZipFile(_io.BytesIO(contenido)) as z:
                nombres = z.namelist()
                shp_n = next((n for n in nombres if n.lower().endswith(".shp")), None)
                shx_n = next((n for n in nombres if n.lower().endswith(".shx")), None)
                dbf_n = next((n for n in nombres if n.lower().endswith(".dbf")), None)
                if not all([shp_n, shx_n, dbf_n]):
                    return [], None

                def _buf(name):
                    data = z.read(name)
                    b = _io.BytesIO(data); b.name = name; b.chunks = lambda: [data]; return b

                geojson_str, stats = procesar_shapefile_a_geojson(
                    {"shp": _buf(shp_n), "shx": _buf(shx_n), "dbf": _buf(dbf_n)}
                )
            bbox = [
                stats.get("bbox_min_lng"), stats.get("bbox_min_lat"),
                stats.get("bbox_max_lng"), stats.get("bbox_max_lat"),
            ]

        elif a.tipo_archivo == "geojson":
            geojson_str = a.archivo.read().decode("utf-8")
            bbox = a.bbox  # ya calculado al cargar

        else:
            return [], None

        features = json.loads(geojson_str).get("features", [])
        return features, bbox
    except Exception:
        return [], None


def _combinar_archivos_bg(nuevo_id, ids_origen):
    """Hilo daemon: fusiona N archivos, recalcula escala global y genera PNG."""
    from django.db import connection
    try:
        archivos = list(ArchivoAnalitico.objects.filter(id__in=ids_origen))
        todos_features = []
        bboxes = []

        for a in archivos:
            features, bbox = _leer_features_archivo(a)
            todos_features.extend(features)
            if bbox and all(v is not None for v in bbox):
                bboxes.append(bbox)

        if not todos_features:
            ArchivoAnalitico.objects.filter(id=nuevo_id).update(estado="error")
            return

        # Bbox global (unión de todas las partes)
        if bboxes:
            bbox_global = [
                min(b[0] for b in bboxes), min(b[1] for b in bboxes),
                max(b[2] for b in bboxes), max(b[3] for b in bboxes),
            ]
        else:
            bbox_global = calcular_bbox(todos_features)

        if not bbox_global:
            ArchivoAnalitico.objects.filter(id=nuevo_id).update(estado="error")
            return

        # Colorización con escala unificada sobre todos los datos
        gj_merged = {"type": "FeatureCollection", "features": todos_features}
        gj_col, leyenda, estadisticas = colorear_geojson(gj_merged)

        png_bytes  = rasterizar_a_png(gj_col, bbox_global)
        gj_str     = json.dumps(gj_col)

        nuevo = ArchivoAnalitico.objects.get(id=nuevo_id)
        nuevo.archivo.save(
            f"combinado_{nuevo_id}.geojson",
            ContentFile(gj_str.encode("utf-8")),
            save=False,
        )
        nuevo.imagen_png.save(
            f"combinado_{nuevo_id}.png",
            ContentFile(png_bytes),
            save=False,
        )
        nuevo.tipo_archivo  = "geojson"
        nuevo.bbox          = bbox_global
        nuevo.leyenda       = leyenda
        nuevo.estadisticas  = estadisticas
        nuevo.estado        = "procesado"
        nuevo.save()

    except Exception:
        ArchivoAnalitico.objects.filter(id=nuevo_id).update(estado="error")
    finally:
        connection.close()


@login_required
@require_POST
def ajax_suelo_combinar(request, campo_id):
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)

    ids_raw = request.POST.getlist("ids[]")
    ids     = [int(i) for i in ids_raw if str(i).isdigit()]
    if len(ids) < 2:
        return JsonResponse({"ok": False, "error": "Seleccioná al menos 2 archivos"}, status=400)

    # Verificar que los archivos pertenecen al campo y tienen imagen
    validos = ArchivoAnalitico.objects.filter(
        id__in=ids, campo=campo, imagen_png__isnull=False
    ).count()
    if validos < 2:
        return JsonResponse({"ok": False, "error": "Archivos no válidos o sin imagen generada"}, status=400)

    # Crear registro pendiente
    nombre_archivo = f"combinado_{campo.nombre}_{date.today()}.geojson"
    nuevo = ArchivoAnalitico.objects.create(
        campo       = campo,
        archivo     = ContentFile(b"{}", name=nombre_archivo),
        tipo_archivo= "geojson",
        cargado_por = request.user,
        estado      = "pendiente",
    )

    threading.Thread(
        target=_combinar_archivos_bg,
        args=(nuevo.id, ids),
        daemon=True,
    ).start()

    return JsonResponse({"ok": True, "id": nuevo.id, "nombre": nombre_archivo})


@login_required
def ajax_suelo_archivo_estado(request, archivo_id):
    """Polling endpoint: devuelve el estado actual de un ArchivoAnalitico."""
    empresa = request.user.profile.empresa
    a = get_object_or_404(ArchivoAnalitico, id=archivo_id, campo__empresa=empresa)
    return JsonResponse({
        "ok":          True,
        "estado":      a.estado,
        "imagen_url":  a.imagen_png.url if a.imagen_png else None,
        "bbox":        a.bbox,
        "leyenda":     a.leyenda,
        "estadisticas":a.estadisticas,
        "nombre":      a.archivo.name.split("/")[-1] if a.archivo else "",
        "fecha":       a.fecha_carga.strftime("%d/%m/%Y"),
    })


@login_required
def ajax_suelo_geojson(request, archivo_id):
    empresa  = request.user.profile.empresa
    registro = get_object_or_404(ArchivoAnalitico, id=archivo_id, campo__empresa=empresa)
    try:
        if registro.tipo_archivo == "shapefile":
            contenido = registro.archivo.read()
            with zipfile.ZipFile(_io.BytesIO(contenido)) as z:
                nombres_zip = z.namelist()
                shp_n = next((n for n in nombres_zip if n.lower().endswith(".shp")), None)
                shx_n = next((n for n in nombres_zip if n.lower().endswith(".shx")), None)
                dbf_n = next((n for n in nombres_zip if n.lower().endswith(".dbf")), None)

                def _buf(name):
                    data = z.read(name)
                    b = _io.BytesIO(data)
                    b.name = name
                    b.chunks = lambda: [data]
                    return b

                geojson_str, stats = procesar_shapefile_a_geojson(
                    {"shp": _buf(shp_n), "shx": _buf(shx_n), "dbf": _buf(dbf_n)}
                )
        elif registro.tipo_archivo == "geojson":
            geojson_str = registro.archivo.read().decode("utf-8")
            stats       = {}
        else:
            return JsonResponse({"ok": False, "error": "Tipo de archivo no soportado para visualización"}, status=400)

        gj = json.loads(geojson_str)
        return JsonResponse({
            "ok":     True,
            "geojson": gj,
            "bbox":   [
                stats.get("bbox_min_lng"), stats.get("bbox_min_lat"),
                stats.get("bbox_max_lng"), stats.get("bbox_max_lat"),
            ],
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


@login_required
@require_POST
def ajax_suelo_medicion_eliminar(request, medicion_id):
    empresa  = request.user.profile.empresa
    medicion = get_object_or_404(MedicionCampo, id=medicion_id, campo__empresa=empresa)
    medicion.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def ajax_suelo_archivo_eliminar(request, archivo_id):
    empresa  = request.user.profile.empresa
    registro = get_object_or_404(ArchivoAnalitico, id=archivo_id, campo__empresa=empresa)
    if registro.imagen_png:
        registro.imagen_png.delete(save=False)
    if registro.archivo:
        registro.archivo.delete(save=False)
    registro.delete()
    return JsonResponse({"ok": True})


# =====================================================
# AJAX — CAPAS ANALÍTICAS
# =====================================================

@login_required
@require_POST
def ajax_capa_procesar(request):
    empresa = request.user.profile.empresa
    form    = CapaMapaForm(request.POST, request.FILES, empresa=empresa)
    if form.is_valid():
        archivo = form.cleaned_data["archivo"]
        nombre  = form.cleaned_data["nombre"]
        extensiones_validas = {".zip", ".shp", ".dbf", ".shx", ".prj", ".kml", ".kmz", ".geojson", ".json"}
        ext = f".{archivo.name.split('.')[-1].lower()}"
        if ext not in extensiones_validas:
            return JsonResponse({"ok": False, "error": "Tipo de archivo no soportado"}, status=400)
        return JsonResponse({"ok": True, "nombre": nombre})
    return JsonResponse({"ok": False, "errors": form.errors.as_json()}, status=400)
