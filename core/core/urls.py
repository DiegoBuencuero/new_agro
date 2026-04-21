from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from agro.views import index,login_page
from gestion_agro.views import (vista_crear_campo, vista_editar_campo, vista_crear_campana, vista_editar_campana,vista_crear_ciclo,
vista_lista_ciclos, vista_detalle_ciclo, vista_editar_ciclo, ajax_get_ciclos_data, vista_agregar_actividad,
 ajax_subtipos_tipo_actividad, ajax_productos_por_actividad, ajax_valores_actividad, vista_lista_stock,
 vista_lista_facturas, vista_cargar_factura, vista_cargar_factura_manual, vista_procesar_pdf_factura,
vista_revisar_factura, vista_confirmar_factura, ajax_unidades_conversion, vista_producto, vista_editar_producto,
ajax_presentaciones_producto, ajax_crear_producto, ajax_crear_presentacion, ajax_crear_producto
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    path('i18n/', include('django.conf.urls.i18n')), 

    path('login/', login_page, name='login'),
    # path('signup/', signup, name='signup'),
    # path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('campos/', vista_crear_campo, name='vista_crear_campo'),
    path('campos/<int:id_campo>/', vista_editar_campo, name='vista_editar_campo'),

    path('campanas/', vista_crear_campana, name='vista_crear_campana'),
    path('campanas/<int:id_campana>/', vista_editar_campana, name='vista_editar_campana'),

    
    path('productos/', vista_producto, name='vista_producto'),
    path('productos/<int:id_prod>/', vista_editar_producto, name='editar_producto'),

    path('ciclos/', vista_lista_ciclos, name='vista_lista_ciclos'),
    path('ciclos/nuevo/', vista_crear_ciclo, name='vista_crear_ciclo'),
    path('ajax/get_ciclos_data/', ajax_get_ciclos_data, name="ajax_get_ciclos_data"),
    path('ciclos/<int:id_ciclo>/', vista_detalle_ciclo, name='vista_detalle_ciclo'),
    path('ciclo/<int:id_ciclo>/actividad/nueva/', vista_agregar_actividad, name="vista_agregar_actividad"),
    path("ajax/subtipos-tipo-actividad/", ajax_subtipos_tipo_actividad, name="ajax_subtipos_tipo_actividad" ),
    path("ajax/productos-por-actividad/", ajax_productos_por_actividad, name="ajax_productos_por_actividad"),
    path( "ajax/valores-actividad/", ajax_valores_actividad, name="ajax_valores_actividad",),

    path('stock/', vista_lista_stock, name='vista_lista_stock'),

    path('facturas/', vista_lista_facturas, name='vista_lista_facturas'),
    path('facturas/add/', vista_cargar_factura, name='vista_cargar_factura'),
    path('facturas/add-manual/', vista_cargar_factura_manual, name='vista_cargar_factura_manual'),
    path('facturas/revisar/', vista_revisar_factura, name='vista_revisar_factura'),
    path("facturas/procesar/", vista_procesar_pdf_factura, name="vista_procesar_pdf_factura"),
    path("facturas/confirmar/", vista_confirmar_factura, name="vista_confirmar_factura"),
    path("ajax/unidades-conversion/", ajax_unidades_conversion, name="ajax_unidades_conversion"),
    path("ajax/presentaciones-producto/", ajax_presentaciones_producto, name="ajax_presentaciones_producto"),
    path("ajax/crear-producto/", ajax_crear_producto, name="ajax_crear_producto"),
    path("ajax/crear-presentacion/", ajax_crear_presentacion, name="ajax_crear_presentacion"),
  
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)