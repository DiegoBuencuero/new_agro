import json
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from gestion_agro.models import Campo, AreaCampo
from .models import CapaAnalisis, NDVICaptura
from .shapefile_utils import (
    procesar_shapefile_a_geojson,
    procesar_kml_a_geojson,
)


# =====================================================
# VISTA PRINCIPAL
# =====================================================

@login_required
def vista_mapa(request):
    empresa = request.user.profile.empresa
    campos = (Campo.objects.filter(empresa=empresa).order_by("nombre"))

    return render( request,
        "temp_mapas/vista_mapa_principal.html", {"empresa": empresa,"campos": campos,},
    )


# =====================================================
# LISTAR CAPAS
# =====================================================

@login_required
def ajax_listar_capas(request, campo_id):
    empresa = request.user.profile.empresa

    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Método no permitido",}, status=405,)
    try:
        campo = Campo.objects.get( id=campo_id, empresa=empresa, )

    except Campo.DoesNotExist:
        return JsonResponse(
            {"ok": False, "error": "Campo no encontrado",},
            status=404,
        )

    capas = campo.capas.all().order_by("-creado")
    data = []

    for capa in capas:
        data.append({
            "id": capa.id,
            "nombre": capa.nombre,
            "tipo": capa.tipo,
            "tipo_display": capa.get_tipo_display(),
            "variable": capa.variable,
            "unidad": capa.unidad,
            "valor_min": capa.valor_min,
            "valor_max": capa.valor_max,
            "valor_promedio": capa.valor_promedio,
            "num_features": capa.num_features,
            "geojson_url": capa.geojson_url,

            "bbox": [
                capa.bbox_min_lng,
                capa.bbox_min_lat,
                capa.bbox_max_lng,
                capa.bbox_max_lat,
            ] if capa.bbox_min_lng is not None else None,

            "creado": capa.creado.strftime(
                "%Y-%m-%d %H:%M"
            ),
        })

    return JsonResponse({
        "ok": True,
        "campo": {
            "id": campo.id,
            "nombre": campo.nombre,
        },
        "capas": data,
    })


# =====================================================
# SUBIR CAPA
# =====================================================

@login_required
def ajax_subir_capa(request, campo_id):
    if request.method != "POST":
        return JsonResponse(
            {"ok": False, "error": "Método no permitido",},
            status=405,
        )

    empresa = request.user.profile.empresa

    try:
        campo = Campo.objects.get(
            id=campo_id,
            empresa=empresa,
        )

    except Campo.DoesNotExist:
        return JsonResponse(
            { "ok": False, "error": "Campo no encontrado", }, status=404,
        )

    # ---------------------------------
    # Validar archivos obligatorios
    # ---------------------------------

    archivos = {}

    for extension in ("shp", "shx", "dbf"):
        archivo = request.FILES.get( extension) 

        if not archivo:
            return JsonResponse(
                {
                    "ok": False,
                    "error": f"Falta archivo .{extension}",
                },
                status=400,
            )

        archivos[extension] = archivo

    # ---------------------------------
    # Datos del formulario
    # ---------------------------------

    nombre = (request.POST.get("nombre", "").strip() or "Capa sin nombre")
    tipo = request.POST.get( "tipo", "otro",).strip().lower()   
    variable = ( request.POST.get("variable", "rate").strip() or "rate")
    unidad = (request.POST.get("unidad", "").strip() or None)

    # ---------------------------------
    # Procesar shapefile
    # ---------------------------------

    try:
        geojson_str, stats = (
            procesar_shapefile_a_geojson(
                archivos,
                nombre_variable=variable,
            )
        )

    except Exception as error:
        return JsonResponse(
            {
                "ok": False,
                "error":
                    "Error procesando shapefile: "
                    + str(error),
            },
            status=400,
        )

    # ---------------------------------
    # Crear nueva capa
    # ---------------------------------

    capa = CapaAnalisis(
        empresa=empresa,
        campo=campo,
        nombre=nombre,
        tipo=tipo,
        variable=variable,
        unidad=unidad,
        creado_por=request.user,

        num_features=stats["num_features"],
        valor_min=stats["valor_min"],
        valor_max=stats["valor_max"],
        valor_promedio=stats["valor_promedio"],

        bbox_min_lng=stats["bbox_min_lng"],
        bbox_min_lat=stats["bbox_min_lat"],
        bbox_max_lng=stats["bbox_max_lng"],
        bbox_max_lat=stats["bbox_max_lat"],
    )

    # ---------------------------------
    # Guardar archivo GeoJSON
    # ---------------------------------

    nombre_archivo = (
        "capa_{}_{}.geojson".format(
            campo.id,
            capa.nombre.replace( " ", "_"))
        )
    

    capa.geojson_file.save(
        nombre_archivo,
        ContentFile(
            geojson_str.encode("utf-8")
        ),
        save=False,
    )

    # Guardar modelo
    capa.save()

    # ---------------------------------
    # Respuesta
    # ---------------------------------

    return JsonResponse({
        "ok": True,
        "message": "Capa creada correctamente",

        "capa": {
            "id": capa.id,
            "nombre": capa.nombre,
            "tipo": capa.tipo,
            "tipo_display":
                capa.get_tipo_display(),
            "variable": capa.variable,
            "unidad": capa.unidad,
            "valor_min": capa.valor_min,
            "valor_max": capa.valor_max,
            "num_features":
                capa.num_features,
            "geojson_url":
                capa.geojson_url,

            "bbox": [
                capa.bbox_min_lng,
                capa.bbox_min_lat,
                capa.bbox_max_lng,
                capa.bbox_max_lat,
            ],
        },
    })


# =====================================================
# ELIMINAR CAPA
# =====================================================

@login_required
def ajax_eliminar_capa(request, capa_id):

    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": "Método no permitido",
            },
            status=405,
        )

    empresa = request.user.profile.empresa

    try:
        capa = CapaAnalisis.objects.get(
            id=capa_id,
            empresa=empresa,
        )

    except CapaAnalisis.DoesNotExist:
        return JsonResponse(
            {
                "ok": False,
                "error": "Capa no encontrada",
            },
            status=404,
        )

    if capa.geojson_file:
        capa.geojson_file.delete(
            save=False
        )

    capa.delete()

    return JsonResponse({
        "ok": True,
        "message": "Capa eliminada",
    })

# =====================================================================
# ÁREAS DEL CAMPO (reemplaza boundary único)
# =====================================================================

@login_required
def ajax_listar_areas(request, campo_id):
    empresa = request.user.profile.empresa
    campo = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    areas = campo.areas.all()
    return JsonResponse({
        "ok": True,
        "areas": [
            {
                "id":           a.id,
                "nombre":       a.nombre,
                "descripcion":  a.descripcion,
                "superficie_ha": float(a.superficie_ha) if a.superficie_ha else None,
                "geojson":      json.loads(a.boundary_geojson) if a.boundary_geojson else None,
            }
            for a in areas
        ],
    })


@login_required
def ajax_crear_area(request, campo_id):
    """Crea un área nueva (sin geometría todavía)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)
    empresa = request.user.profile.empresa
    campo = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    body = json.loads(request.body)
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
def ajax_guardar_area_geojson(request, area_id):
    """Guarda el GeoJSON dibujado para un área."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)
    empresa = request.user.profile.empresa
    area = get_object_or_404(AreaCampo, id=area_id, campo__empresa=empresa)
    try:
        body   = json.loads(request.body)
        geojson = body.get("geojson")
        if not geojson:
            return JsonResponse({"ok": False, "error": "GeoJSON vacío"}, status=400)
        superficie = body.get("superficie_ha")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)
    area.boundary_geojson = json.dumps(geojson)
    if superficie:
        area.superficie_ha = superficie
    area.save()
    return JsonResponse({"ok": True, "message": "Área guardada"})


@login_required
def ajax_cargar_area_shapefile(request, campo_id):
    """Sube un shapefile y crea un AreaCampo nuevo."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)
    empresa = request.user.profile.empresa
    campo = get_object_or_404(Campo, id=campo_id, empresa=empresa)

    archivos = {}
    for ext in ("shp", "shx", "dbf"):
        f = request.FILES.get(ext)
        if not f:
            return JsonResponse({"ok": False, "error": f"Falta archivo .{ext}"}, status=400)
        archivos[ext] = f

    nombre = (request.POST.get("nombre") or "").strip() or f"Área {campo.areas.count() + 1}"

    try:
        geojson_str, stats = procesar_shapefile_a_geojson(archivos, variable_name="area")
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Error procesando shapefile: {e}"}, status=400)

    area = AreaCampo.objects.create(
        campo=campo,
        nombre=nombre,
        boundary_geojson=geojson_str,
        superficie_ha=stats.get("superficie_ha"),
    )

    return JsonResponse({
        "ok":     True,
        "id":     area.id,
        "nombre": area.nombre,
        "geojson": json.loads(geojson_str),
        "bbox": [stats.get("bbox_min_lng"), stats.get("bbox_min_lat"),
                 stats.get("bbox_max_lng"), stats.get("bbox_max_lat")],
    })


@login_required
def ajax_cargar_area_kml(request, campo_id):
    """Sube un archivo KML o KMZ y crea un AreaCampo."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)
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
        boundary_geojson=geojson_str,
        superficie_ha=stats.get("superficie_ha"),
    )

    return JsonResponse({
        "ok":     True,
        "id":     area.id,
        "nombre": area.nombre,
        "geojson": json.loads(geojson_str),
        "bbox": [stats.get("bbox_min_lng"), stats.get("bbox_min_lat"),
                 stats.get("bbox_max_lng"), stats.get("bbox_max_lat")],
    })


@login_required
def ajax_eliminar_area(request, area_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)
    empresa = request.user.profile.empresa
    area = get_object_or_404(AreaCampo, id=area_id, campo__empresa=empresa)
    area.delete()
    return JsonResponse({"ok": True})


# mantener para compatibilidad con NDVI (usa boundary_geojson del campo)
@login_required
def ajax_get_boundary(request, campo_id):
    empresa = request.user.profile.empresa
    campo = get_object_or_404(Campo, id=campo_id, empresa=empresa)
    union = campo.areas_geojson_union
    if not union["features"]:
        return JsonResponse({"ok": True, "geojson": None})
    return JsonResponse({"ok": True, "geojson": union})


# =====================================================================
# NDVI
# =====================================================================

@login_required
def ajax_fetch_ndvi_campo(request, campo_id):
    """Ejecuta la consulta NDVI para un campo desde la UI."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)

    from mapas.management.commands.fetch_ndvi import geojson_union_areas
    if not geojson_union_areas(campo) and not campo.boundary_geojson:
        return JsonResponse({"ok": False, "error": "El campo no tiene áreas ni contorno definido."}, status=400)

    try:
        from mapas.management.commands.fetch_ndvi import _get_sh_config, procesar_campo
        config = _get_sh_config()
    except RuntimeError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    except ImportError:
        return JsonResponse({"ok": False, "error": "Librería sentinelhub no instalada. Ejecutá: pip install sentinelhub Pillow numpy"}, status=400)

    from datetime import date, timedelta

    class Log:
        def __init__(self): self.lines = []
        def write(self, s): self.lines.append(str(s))

    log = Log()
    fecha_hasta = date.today()

    forzar = request.POST.get("forzar") == "1"

    ultima = NDVICaptura.objects.filter(campo=campo).order_by("-fecha_imagen").first()

    if forzar and ultima:
        # Borrar la última captura para regenerarla limpia
        if ultima.imagen_png:
            ultima.imagen_png.delete(save=False)
        ultima.delete()
        ultima = None

    if ultima and not forzar:
        fecha_desde = ultima.fecha_imagen + timedelta(days=1)
        if fecha_desde > fecha_hasta:
            return JsonResponse({
                "ok": True,
                "sin_nuevas": True,
                "log": [f"La última captura es del {ultima.fecha_imagen}. No hay imágenes nuevas disponibles."],
                "ultima_captura": None,
            })
    else:
        fecha_desde = fecha_hasta - timedelta(days=5)

    try:
        procesar_campo(campo, fecha_desde, fecha_hasta, config, log)
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Error al consultar CDSE: {e}", "log": log.lines}, status=500)

    captura = NDVICaptura.objects.filter(campo=campo).order_by("-fecha_imagen").first()
    resultado = None
    if captura:
        resultado = {
            "fecha":         str(captura.fecha_imagen),
            "ndvi_promedio": captura.ndvi_promedio,
            "ndvi_min":      captura.ndvi_min,
            "ndvi_max":      captura.ndvi_max,
            "nubosidad":     captura.nubosidad_pct,
            "estado":        captura.estado,
            "imagen_url":    captura.imagen_png.url if captura.imagen_png else None,
        }

    return JsonResponse({"ok": True, "log": log.lines, "ultima_captura": resultado})


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
    return render(request, "temp_mapas/ndvi_campo.html", {"campos": campos, "leyenda_ndvi": leyenda})


@login_required
def ajax_ndvi_data(request, campo_id):
    """Serie temporal NDVI de un campo — para Chart.js."""
    empresa = request.user.profile.empresa
    campo   = get_object_or_404(Campo, id=campo_id, empresa=empresa)

    capturas = NDVICaptura.objects.filter(campo=campo).order_by("fecha_imagen")

    data = [
        {
            "fecha":         str(c.fecha_imagen),
            "ndvi_promedio": c.ndvi_promedio,
            "ndvi_min":      c.ndvi_min,
            "ndvi_max":      c.ndvi_max,
            "nubosidad":     c.nubosidad_pct,
            "estado":        c.estado,
            "imagen_url":    c.imagen_png.url if c.imagen_png else None,
            "origen":        c.origen,
        }
        for c in capturas
    ]

    from mapas.management.commands.fetch_ndvi import _bbox_from_geojson, geojson_union_areas
    import json as _json
    geojson_str = geojson_union_areas(campo) or campo.boundary_geojson
    bbox = None
    area_geojson = None
    if geojson_str:
        try:
            sh_bbox = _bbox_from_geojson(geojson_str)
            bbox = [sh_bbox.min_y, sh_bbox.min_x, sh_bbox.max_y, sh_bbox.max_x]
            area_geojson = _json.loads(geojson_str)
        except Exception:
            pass

    return JsonResponse({
        "ok":          True,
        "campo":       {"id": campo.id, "nombre": campo.nombre},
        "tiene_area":  bool(geojson_str),
        "bbox":        bbox,
        "area_geojson": area_geojson,
        "capturas":    data,
    })
