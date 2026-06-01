---
name: project-new-agro
description: "Estado, modelos, flujos y decisiones de arquitectura del sistema agropecuario Django new_agro"
metadata: 
  node_type: memory
  type: project
  originSessionId: a5bf8fd7-c79f-4495-913c-bd3d5079d004
---

Proyecto Django en `/home/diego/Work/Django/new_agro/core/`. Sistema de gestión agropecuaria.

**Why:** Sistema para gestionar ciclos agrícolas, cosechas, stock, compras, ventas y análisis GIS de una empresa agropecuaria.

## Apps principales
- `agro`: empresa, usuarios, unidades, conversiones
- `gestion_agro`: ciclos, actividades, stock, productos, depósitos
- `administracion`: facturas compra/venta, pagos, cobros
- `mapas`: análisis GIS, NDVI, capas de suelo, comparación

## Módulo mapas — arquitectura y modelos

### Modelos clave (mapas app)
- `VariableAnalitica`: tipos suelo/cosecha/satelite/otro
- `ArchivoAnalitico`: campo + variable(null) + archivo + imagen_png (PNG rasterizado) + bbox + leyenda + estadisticas JSON {min,max,prom,std}
  - variable=None → asumido tipo "suelo" en _archivo_a_dict_capa (solo cosecha siempre tiene variable)
- `MedicionCampo`: campo + variable + fecha + promedio (no se crea automáticamente en uploads, solo para NDVI histórico)
- `CapturaSatelite` + `IndiceVegetacion`: NDVI con imagen_png + promedio/minimo/maximo
  - IndiceVegetacion NO guarda grilla_datos → no regenerable sin re-fetch a Sentinel
  - bbox de NDVI se calcula desde campo.contorno (IndiceVegetacion no tiene bbox propio)

### NDVI (aux_sentenial.py)
- AOI para Sentinel-2 = geojson_union_areas(campo) → fallback campo.contorno
- Borde campo en PNG: ancho = max(1, w//400), alpha=120 (sutil, semitransparente)
- Borde ciclo en PNG: ancho = max(1, w//350), alpha=150 (amarillo semitransparente)
- Imágenes existentes requieren re-procesar para ver cambio de borde

### Vista Comparación de capas (vista_comparacion)
- URL: /mapas/comparacion/ (sin campo_id en URL)
- Selector de campo en sidebar → AJAX a /mapas/ajax/comparacion/<campo_id>/capas/
- ajax_comparacion_capas devuelve: ArchivoAnalitico + IndiceVegetacion del campo + flag tiene_simulacion
- tiene_simulacion=True solo si existe archivo cosecha_simulada_<CAMPO>.geojson en staticfiles
- Cosecha simulada solo existe para IBICUI (campo_id=4)
- IDs de capas: int para ArchivoAnalitico, string "ndvi_N" para IndiceVegetacion
- Leaflet: minZoom=6, maxZoom=17
- Click: clickMarkers array limpiado en cada nuevo click (un solo puntero visible)
- URLs JS generadas con Django {% url %} y placeholder 0: _URL_CAPAS.replace("/0/", `/${id}/`)
- "Comparar capas" aparece como nav-tab entre "NDVI/Satélite" y "Comparación" en vista_mapas

### Comparación tab inline en vista_mapas
- vista_mapas computa comp_variables, comp_periodos, comp_areas, comp_tendencia, comp_filas, comp_fechas
- Agrupa ArchivoAnalitico procesados por (variable_label, area_label) y fecha_carga.date()

## Módulo administración — pagos y cobros

### Modelos
- Pago: proveedor, numero, fecha (DateField), medio_pago, referencia, aplicaciones → facturas
- Recibo: cliente, numero, fecha (DateField), medio_cobro, referencia, aplicaciones → facturas ventas
- Comprobantes como páginas HTML standalone (no extienden base.html)

### UI cuenta corriente
- Sticky action bar que cambia color al seleccionar facturas
- Modal pago/cobro: max-width 640px, multi-factura con monto parcial
- Botón "Pagar" / "Cobrar"

## Reglas de template (base.html)
- Bloques: plugin_css (head), content, plugin_js, custom_js (fin del body)
- NO existe block extra_js — usar custom_js

## Migraciones importantes
- gestion_agro 0036: contorno en Campo/AreaCampo/CicloAgricola + ciclo en AreaCampo
- administracion 0010: Recibo upgrades (numero, fecha DateField, medio_cobro, referencia)
- mapas 0003: modelos nuevos de análisis GIS

## Reglas de negocio
- Una siembra por fase abierta, múltiples por ciclo
- Cosecha cierra la fase automáticamente
- Stock en 2 filas por producto: Semilla (M) y Consumo (C)
- Traducciones: ES + PT, correr makemessages + compilemessages al agregar strings
