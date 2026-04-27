from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import render

from gestion_agro.models import Campo
from .models import CapaAnalisis
from .shapefile_utils import procesar_shapefile_a_geojson


@login_required
def vista_mapa(request):
    """Vista principal: HTML con mapa. Los datos se piden por AJAX."""
    empresa = request.user.profile.empresa
    campos = Campo.objects.filter(empresa=empresa).order_by("nombre")
    return render(
        request,
        "temp_mapas/vista_mapa_principal.html",
        {"empresa": empresa, "campos": campos},
    )


# =====================================================================
# AJAX endpoints (mismo patrón que ajax_agregar_producto_final)
# =====================================================================


@login_required
def ajax_listar_capas(request, campo_id):
    """Devuelve las capas de un campo."""
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    empresa = request.user.profile.empresa
    try:
        campo = Campo.objects.get(id=campo_id, empresa=empresa)
    except Campo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Campo no encontrado"}, status=404)

    capas = campo.capas.all().order_by("-creado")
    data = []
    for c in capas:
        data.append({
            "id": c.id,
            "nombre": c.nombre,
            "tipo": c.tipo,
            "tipo_display": c.get_tipo_display(),
            "variable": c.variable,
            "unidad": c.unidad,
            "valor_min": c.valor_min,
            "valor_max": c.valor_max,
            "valor_promedio": c.valor_promedio,
            "num_features": c.num_features,
            "geojson_url": c.geojson_url,
            "bbox": [c.bbox_min_lng, c.bbox_min_lat, c.bbox_max_lng, c.bbox_max_lat]
                    if c.bbox_min_lng is not None else None,
            "creado": c.creado.strftime("%Y-%m-%d %H:%M"),
        })

    return JsonResponse({
        "ok": True,
        "campo": {"id": campo.id, "nombre": campo.nombre},
        "capas": data,
    })


@login_required
def ajax_subir_capa(request, campo_id):
    """Sube los 3 archivos del shapefile y los procesa a GeoJSON."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    empresa = request.user.profile.empresa
    try:
        campo = Campo.objects.get(id=campo_id, empresa=empresa)
    except Campo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Campo no encontrado"}, status=404)

    archivos = {}
    for ext in ("shp", "shx", "dbf"):
        f = request.FILES.get(ext)
        if not f:
            return JsonResponse(
                {"ok": False, "error": "Falta archivo ." + ext},
                status=400,
            )
        archivos[ext] = f

    nombre = request.POST.get("nombre", "").strip() or "Capa sin nombre"
    tipo = request.POST.get("tipo", "otro")
    variable = request.POST.get("variable", "rate").strip() or "rate"
    unidad = request.POST.get("unidad", "").strip()

    try:
        geojson_str, stats = procesar_shapefile_a_geojson(archivos, variable_name=variable)
    except Exception as e:
        return JsonResponse(
            {"ok": False, "error": "Error procesando shapefile: " + str(e)},
            status=400,
        )

    capa = CapaAnalisis(
        empresa=empresa,
        campo=campo,
        nombre=nombre,
        tipo=tipo,
        variable=variable,
        unidad=unidad,
        creado_por=request.user,
        **stats,
    )
    filename = "capa_{}_{}.geojson".format(campo.id, capa.nombre.replace(" ", "_"))
    capa.geojson_file.save(filename, ContentFile(geojson_str.encode("utf-8")), save=False)
    capa.save()

    return JsonResponse({
        "ok": True,
        "message": "Capa creada correctamente",
        "capa": {
            "id": capa.id,
            "nombre": capa.nombre,
            "tipo": capa.tipo,
            "tipo_display": capa.get_tipo_display(),
            "variable": capa.variable,
            "unidad": capa.unidad,
            "valor_min": capa.valor_min,
            "valor_max": capa.valor_max,
            "num_features": capa.num_features,
            "geojson_url": capa.geojson_url,
            "bbox": [capa.bbox_min_lng, capa.bbox_min_lat,
                     capa.bbox_max_lng, capa.bbox_max_lat],
        },
    })


@login_required
def ajax_eliminar_capa(request, capa_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    empresa = request.user.profile.empresa
    try:
        capa = CapaAnalisis.objects.get(id=capa_id, empresa=empresa)
    except CapaAnalisis.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Capa no encontrada"}, status=404)

    if capa.geojson_file:
        capa.geojson_file.delete(save=False)
    capa.delete()

    return JsonResponse({"ok": True, "message": "Capa eliminada"})
