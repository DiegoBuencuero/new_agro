from django.urls import path
from . import views

urlpatterns = [
    # Vistas principales
    path("mapas/",  views.vista_mapas, name="vista_mapas"),
    path("ndvi/",   views.vista_ndvi,  name="vista_ndvi"),

    # NDVI
    path("ndvi/<int:campo_id>/procesar/", views.vista_ndvi_procesar, name="vista_ndvi_procesar"),
    path("ajax/ndvi/<int:campo_id>/serie/", views.ajax_ndvi_serie,   name="ajax_ndvi_serie"),

    # Áreas del campo
    path("ajax/areas/<int:campo_id>/",               views.ajax_areas_listar,          name="ajax_areas_listar"),
    path("ajax/area/<int:campo_id>/crear/",           views.ajax_area_crear,            name="ajax_area_crear"),
    path("ajax/area/<int:area_id>/guardar-geojson/",  views.ajax_area_guardar_geojson,  name="ajax_area_guardar_geojson"),
    path("ajax/area/<int:area_id>/eliminar/",         views.ajax_area_eliminar,         name="ajax_area_eliminar"),
    path("ajax/area/<int:campo_id>/shapefile/",       views.ajax_area_cargar_shapefile, name="ajax_area_cargar_shapefile"),
    path("ajax/area/<int:campo_id>/kml/",             views.ajax_area_cargar_kml,       name="ajax_area_cargar_kml"),

    # Contorno / boundary
    path("ajax/boundary/<int:campo_id>/",  views.ajax_boundary,         name="ajax_boundary"),
    path("ajax/contorno/parsear/",         views.ajax_contorno_parsear, name="ajax_contorno_parsear"),

    # Suelo
    path("ajax/suelo/<int:campo_id>/listar/",                   views.ajax_suelo_listar,            name="ajax_suelo_listar"),
    path("ajax/suelo/<int:campo_id>/cargar/",                   views.ajax_suelo_cargar,            name="ajax_suelo_cargar"),
    path("ajax/suelo/<int:campo_id>/archivos/",                 views.ajax_suelo_archivos,          name="ajax_suelo_archivos"),
    path("ajax/suelo/archivo/<int:archivo_id>/geojson/",        views.ajax_suelo_geojson,           name="ajax_suelo_geojson"),
    path("ajax/suelo/archivo/<int:archivo_id>/clic/",           views.ajax_suelo_clic,              name="ajax_suelo_clic"),
    path("ajax/suelo/medicion/<int:medicion_id>/eliminar/",     views.ajax_suelo_medicion_eliminar, name="ajax_suelo_medicion_eliminar"),
    path("ajax/suelo/<int:campo_id>/combinar/",                 views.ajax_suelo_combinar,          name="ajax_suelo_combinar"),
    path("ajax/suelo/archivo/<int:archivo_id>/estado/",         views.ajax_suelo_archivo_estado,    name="ajax_suelo_archivo_estado"),
    path("ajax/suelo/archivo/<int:archivo_id>/regenerar/",      views.ajax_suelo_regenerar,         name="ajax_suelo_regenerar"),
    path("ajax/suelo/archivo/<int:archivo_id>/eliminar/",      views.ajax_suelo_archivo_eliminar,  name="ajax_suelo_archivo_eliminar"),

    # Capas analíticas
    path("ajax/capa/procesar/", views.ajax_capa_procesar, name="ajax_capa_procesar"),

    # Cosecha
    path("ajax/cosecha/<int:campo_id>/cargar/",  views.ajax_cosecha_cargar,  name="ajax_cosecha_cargar"),
    path("ajax/cosecha/<int:campo_id>/archivos/", views.ajax_cosecha_archivos, name="ajax_cosecha_archivos"),
    path("ajax/cosecha/<int:campo_id>/simular/", views.ajax_cosecha_simular,  name="ajax_cosecha_simular"),

    # Comparación
    path("ajax/comparacion/<int:campo_id>/capas/", views.ajax_comparacion_capas, name="ajax_comparacion_capas"),
    path("ajax/comparacion/<int:campo_id>/punto/", views.ajax_comparacion_punto, name="ajax_comparacion_punto"),
    path("comparacion/",                           views.vista_comparacion,      name="vista_comparacion"),
    path("ajax/<int:campo_id>/analisis-punto/",    views.ajax_analisis_punto,     name="ajax_analisis_punto"),
    path("lluvia/",                                views.vista_registros_lluvia,  name="vista_registros_lluvia"),
    path("lluvia/<int:medicion_id>/eliminar/",     views.ajax_eliminar_lluvia,    name="ajax_eliminar_lluvia"),
]
