from django.urls import path
from . import views

urlpatterns = [
    path("", views.vista_mapa, name="vista_mapas"),

    # Capas de análisis
    path("ajax/capas/<int:campo_id>/",        views.ajax_listar_capas,            name="ajax_listar_capas"),
    path("ajax/capa/subir/<int:campo_id>/",   views.ajax_subir_capa,              name="ajax_subir_capa"),
    path("ajax/capa/eliminar/<int:capa_id>/", views.ajax_eliminar_capa,           name="ajax_eliminar_capa"),

    # Áreas del campo
    path("ajax/areas/<int:campo_id>/",             views.ajax_listar_areas,           name="ajax_listar_areas"),
    path("ajax/areas/<int:campo_id>/crear/",       views.ajax_crear_area,             name="ajax_crear_area"),
    path("ajax/areas/<int:campo_id>/shapefile/",   views.ajax_cargar_area_shapefile,  name="ajax_cargar_area_shapefile"),
    path("ajax/areas/<int:campo_id>/kml/",         views.ajax_cargar_area_kml,         name="ajax_cargar_area_kml"),
    path("ajax/area/<int:area_id>/geojson/",       views.ajax_guardar_area_geojson,   name="ajax_guardar_area_geojson"),
    path("ajax/area/<int:area_id>/eliminar/",      views.ajax_eliminar_area,          name="ajax_eliminar_area"),
    # Boundary legacy (usado por NDVI)
    path("ajax/boundary/<int:campo_id>/",          views.ajax_get_boundary,           name="ajax_get_boundary"),

    # NDVI
    path("ndvi/",                             views.vista_ndvi,            name="vista_ndvi"),
    path("ajax/ndvi/<int:campo_id>/",         views.ajax_ndvi_data,        name="ajax_ndvi_data"),
    path("ajax/ndvi/<int:campo_id>/fetch/",   views.ajax_fetch_ndvi_campo, name="ajax_fetch_ndvi_campo"),
]
