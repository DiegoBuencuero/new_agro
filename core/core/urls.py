from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from agro.views import (index, login_page, vista_configuracion, vista_registro, vista_cuenta_suspendida, vista_parametros_actividades,
    ajax_cotizaciones, ajax_dashboard_resumen, ajax_dashboard_calendario, ajax_dashboard_vencimientos)
from administracion.views import (vista_registrar_venta, vista_lista_ventas, ajax_registrar_cobro,
    vista_gestion_facturas, ajax_indicadores_proveedor,
    ajax_buscar_facturas, ajax_registrar_pago, ajax_buscar_pagos, ajax_detalle_pago,
    vista_cargar_factura_venta_manual, ajax_info_producto_venta, ajax_depositos_producto_destino,
    vista_cuenta_corriente_proveedor, vista_cuenta_corriente_cliente,
    vista_comprobante_pago, vista_comprobante_recibo)
from gestion_agro.views import (ajax_agregar_producto_final, ajax_crear_cultivo, ajax_crear_campana, ajax_crear_unidad, ajax_crear_producto_desde_cultivo, ajax_info_cultivo, ajax_areas_por_campo, ajax_unidades_por_base, ajax_variedades_cultivo, vista_crear_campo, ajax_eliminar_insumo, ajax_editar_insumo, vista_resumo_economico, ajax_eliminar_actividad, vista_editar_ciclo, ajax_eliminar_ciclo,
vista_editar_campo, vista_crear_campana, vista_editar_campana,vista_crear_ciclo,
vista_lista_ciclos, vista_detalle_ciclo, ajax_get_ciclos_data, vista_agregar_actividad,
ajax_subtipos_tipo_actividad, ajax_productos_por_actividad, ajax_valores_actividad, vista_lista_stock,
vista_lista_facturas, vista_cargar_factura, vista_cargar_factura_manual, vista_procesar_pdf_factura,
vista_revisar_factura, vista_confirmar_factura, ajax_unidades_conversion, vista_producto, vista_editar_producto,
ajax_presentaciones_producto, ajax_crear_producto, ajax_crear_presentacion, vista_movimientos_producto,
vista_crear_cultivo, vista_editar_cultivo, vista_crear_deposito, vista_editar_deposito, ajax_transferir_stock
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    path('ajax/cotizaciones/', ajax_cotizaciones, name='ajax_cotizaciones'),
    path('ajax/dashboard/resumen/', ajax_dashboard_resumen, name='ajax_dashboard_resumen'),
    path('ajax/dashboard/calendario/', ajax_dashboard_calendario, name='ajax_dashboard_calendario'),
    path('ajax/dashboard/vencimientos/', ajax_dashboard_vencimientos, name='ajax_dashboard_vencimientos'),
    path('i18n/', include('django.conf.urls.i18n')), 

    path('accounts/', include('django.contrib.auth.urls')),
    path('login/', login_page, name='login'),
    path('registro/', vista_registro, name='registro'),
    path('cuenta-suspendida/', vista_cuenta_suspendida, name='cuenta_suspendida'),

    path('campos/', vista_crear_campo, name='vista_crear_campo'),
    path('campos/<int:id_campo>/', vista_editar_campo, name='vista_editar_campo'),
    path('campanas/', vista_crear_campana, name='vista_crear_campana'),
    path('campanas/<int:id_campana>/', vista_editar_campana, name='vista_editar_campana'),
    path('depositos/', vista_crear_deposito, name='vista_crear_deposito'),
    path('depositos/<int:id_deposito>/', vista_editar_deposito, name='vista_editar_deposito'),

    path("cultivos/", vista_crear_cultivo, name="vista_crear_cultivo"),
    path("cultivos/editar/<int:id_cultivo>/", vista_editar_cultivo, name="vista_editar_cultivo"),
    path("ajax/cultivos/<int:cultivo_id>/agregar-producto-final/", ajax_agregar_producto_final, name="ajax_agregar_producto_final"),
    path("ajax/cultivos/crear/", ajax_crear_cultivo, name="ajax_crear_cultivo"),
    path("ajax/campanas/crear/", ajax_crear_campana, name="ajax_crear_campana"),
    path("ajax/unidades/crear/", ajax_crear_unidad, name="ajax_crear_unidad"),

    path('productos/', vista_producto, name='vista_producto'),
    path('productos/<int:id_prod>/', vista_editar_producto, name='editar_producto'),
    path("ajax/crear-producto-desde-cultivo/", ajax_crear_producto_desde_cultivo, name="ajax_crear_producto_desde_cultivo"),
    path("ajax/crear-producto/", ajax_crear_producto, name="ajax_crear_producto"),

    path('ciclos/', vista_lista_ciclos, name='vista_lista_ciclos'),
    path('ciclos/nuevo/', vista_crear_ciclo, name='vista_crear_ciclo'),
    path("ajax/info-cultivo/", ajax_info_cultivo, name="ajax_info_cultivo"),
    path("ajax/areas-por-campo/", ajax_areas_por_campo, name="ajax_areas_por_campo"),
    path('ajax/get_ciclos_data/', ajax_get_ciclos_data, name="ajax_get_ciclos_data"),
    path('ciclos/<int:id_ciclo>/',          vista_detalle_ciclo, name='vista_detalle_ciclo'),
    path('ciclos/<int:id_ciclo>/editar/',   vista_editar_ciclo,  name='vista_editar_ciclo'),
    path('ciclos/<int:id_ciclo>/eliminar/', ajax_eliminar_ciclo, name='ajax_eliminar_ciclo'),
    path('ciclo/<int:id_ciclo>/actividad/nueva/', vista_agregar_actividad, name="vista_agregar_actividad"),
    path("ajax/subtipos-tipo-actividad/", ajax_subtipos_tipo_actividad, name="ajax_subtipos_tipo_actividad" ),
    path("ajax/productos-por-actividad/", ajax_productos_por_actividad, name="ajax_productos_por_actividad"),
    path("ajax/valores-actividad/", ajax_valores_actividad, name="ajax_valores_actividad",),

    path("stock/", vista_lista_stock, name="vista_lista_stock"),
    path("stock/producto/<int:producto_id>/movimientos/", vista_movimientos_producto, name="vista_movimientos_producto"),

    path('facturas/', vista_lista_facturas, name='vista_lista_facturas'),
    path('facturas/add/', vista_cargar_factura, name='vista_cargar_factura'),
    path('facturas/add-manual/', vista_cargar_factura_manual, name='vista_cargar_factura_manual'),
    path('facturas/revisar/', vista_revisar_factura, name='vista_revisar_factura'),
    path("facturas/procesar/", vista_procesar_pdf_factura, name="vista_procesar_pdf_factura"),
    path("facturas/confirmar/", vista_confirmar_factura, name="vista_confirmar_factura"),
    path("ajax/unidades-conversion/", ajax_unidades_conversion, name="ajax_unidades_conversion"),
    path("ajax/presentaciones-producto/", ajax_presentaciones_producto, name="ajax_presentaciones_producto"),
    path("ajax/transferir-stock/", ajax_transferir_stock, name="ajax_transferir_stock"),
    path("ajax/crear-presentacion/", ajax_crear_presentacion, name="ajax_crear_presentacion"),
    path("ajax/variedades-cultivo/", ajax_variedades_cultivo, name="ajax_variedades_cultivo"),
    path("ajax/unidades-por-base/", ajax_unidades_por_base, name="ajax_unidades_por_base"),
    path("ajax/insumo/<int:insumo_id>/eliminar/", ajax_eliminar_insumo,    name="ajax_eliminar_insumo"),
    path("ajax/insumo/<int:insumo_id>/editar/",   ajax_editar_insumo,     name="ajax_editar_insumo"),
    path("resultados/resumo/",                      vista_resumo_economico,  name="vista_resumo_economico"),
    path("ajax/actividad/<int:actividad_id>/eliminar/", ajax_eliminar_actividad, name="ajax_eliminar_actividad"),

    path('mapas/', include('mapas.urls')),

    path('configuracion/', vista_configuracion, name='vista_configuracion'),
    path('configuracion/actividades/', vista_parametros_actividades, name='vista_parametros_actividades'),

    path('ventas/', vista_lista_ventas, name='vista_lista_ventas'),
    path('ventas/nueva/', vista_registrar_venta, name='vista_registrar_venta'),
    path('ventas/cargar/', vista_cargar_factura_venta_manual, name='vista_cargar_factura_venta_manual'),
    path('ajax/info-producto-venta/', ajax_info_producto_venta, name='ajax_info_producto_venta'),
    path('ajax/depositos-producto-destino/', ajax_depositos_producto_destino, name='ajax_depositos_producto_destino'),
    path('ventas/cobro/', ajax_registrar_cobro, name='ajax_registrar_cobro'),
    path('proveedores/cuenta-corriente/', vista_cuenta_corriente_proveedor, name='vista_cuenta_corriente_proveedor'),
    path('clientes/cuenta-corriente/', vista_cuenta_corriente_cliente, name='vista_cuenta_corriente_cliente'),
    path('administracion/gestion-facturas/', vista_gestion_facturas, name='vista_gestion_facturas'),
    path('administracion/ajax/indicadores-proveedor/', ajax_indicadores_proveedor, name='ajax_indicadores_proveedor'),
    path('administracion/ajax/buscar-facturas/', ajax_buscar_facturas, name='ajax_buscar_facturas'),
    path('administracion/ajax/registrar-pago/', ajax_registrar_pago, name='ajax_registrar_pago'),
    path('administracion/ajax/buscar-pagos/', ajax_buscar_pagos, name='ajax_buscar_pagos'),
    path('administracion/ajax/detalle-pago/<int:pago_id>/', ajax_detalle_pago, name='ajax_detalle_pago'),
    path('administracion/comprobante-pago/<int:pago_id>/', vista_comprobante_pago, name='vista_comprobante_pago'),
    path('administracion/comprobante-recibo/<int:recibo_id>/', vista_comprobante_recibo, name='vista_comprobante_recibo'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)