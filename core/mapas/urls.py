from django.urls import path
from . import views

urlpatterns = [
    path("", views.vista_mapa, name="vista_mapa"),

    path("ajax/capas/<int:campo_id>/", views.ajax_listar_capas, name="ajax_listar_capas"),
    path("ajax/capa/subir/<int:campo_id>/", views.ajax_subir_capa, name="ajax_subir_capa"),
    path("ajax/capa/eliminar/<int:capa_id>/", views.ajax_eliminar_capa, name="ajax_eliminar_capa"),
]
