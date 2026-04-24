"""
=========================================================
URLS — Grupo de Servicio
=========================================================

Agregar estas rutas en urls.py de la app correspondiente
(reproduccion/urls.py o donde las tengas).

Si estás usando un urls.py único por proyecto, incluilas
directamente ahí.

REQUISITO IMPORTANTE:
El name 'ajax_rodeos_por_establecimiento' tiene que coincidir
con el usado en el template (grupo_servicio_form.html).
"""

from django.urls import path
from .views import (
    GrupoServicioCreateView,
    GrupoServicioUpdateView,
    ajax_rodeos_por_establecimiento,
)

urlpatterns = [
    # ---------- Grupo de servicio ----------
    path(
        "grupos/nuevo/",
        GrupoServicioCreateView.as_view(),
        name="grupo_servicio_create",
    ),
    path(
        "grupos/<int:pk>/editar/",
        GrupoServicioUpdateView.as_view(),
        name="grupo_servicio_update",
    ),

    # ---------- Endpoints AJAX ----------
    path(
        "ajax/rodeos-por-establecimiento/",
        ajax_rodeos_por_establecimiento,
        name="ajax_rodeos_por_establecimiento",
    ),
]
