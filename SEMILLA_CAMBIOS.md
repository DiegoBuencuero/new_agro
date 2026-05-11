# Módulo Separación Semilla / Consumo — Documentación de cambios

## Contexto

La cooperativa realiza multiplicación de semilla de soja. Durante el ciclo agrícola un inspector aprueba o rechaza el lote. Al momento de la cosecha, el sistema debe dividir automáticamente el total cosechado en dos movimientos de stock: **semilla certificada** y **grano consumo**. La conversión entre semillas y kg se hace usando el PMG (peso de mil granos) de cada variedad.

---

## 1. Modelos modificados

### `gestion_agro/models.py`

#### `CamposInspeccion` (nuevo — antes tenía un bug crítico)
- FK `um` apuntaba a `'UM'` (modelo inexistente) → corregido a `'agro.Unidad'`
- `related_name` tenía un espacio → corregido a `'inspeccion_unidad_medida'`
- Agregado campo `resultado` con choices `APROBADO / RECHAZADO`
- Renombrado label de `cant_semilla_mult_ha` a "Semillas aprobadas (por ha)"
- **Por qué:** el inspector aprueba una población de semillas por hectárea, no kg

#### `ActividadInsumo`
- Agregado campo `densidad_siembra` (semillas/ha)
- **Por qué:** se auto-calcula al guardar usando `dosis × 1.000.000 / PMG`, se guarda para usar en cálculos posteriores. No lo carga el usuario.

#### `CamposCosecha`
- Agregados campos `kg_semilla` y `kg_consumo`
- **Por qué:** registran el resultado del split para mostrarlo en el detalle del ciclo

#### `TipoActividad`
- Agregado campo `requiere_inspeccion` (BooleanField)
- **Por qué:** permite marcar un tipo de actividad como "Inspección de semilla" sin hardcodear el nombre en el código

#### `Variedad`
- Agregado campo `pmg` (peso de mil granos, en gramos)
- **Por qué:** el PMG es una característica de la variedad, no del producto. Es el pivote para convertir semillas ↔ kg. Se carga al editar el producto semilla de cada variedad.

### `agro/models.py`

#### `Unidad`
- Agregado campo `requiere_pmg` (BooleanField)
- **Por qué:** cuando la unidad de inspección es "semillas", no existe un factor fijo de conversión a kg (depende del PMG de la variedad). Este flag indica al sistema que use PMG en vez de `ConversionUM`. Para unidades estándar (qq, tn, kg) queda en False y usa la tabla de conversiones normal.

#### `Empresa`
- Agregado campo `unidad_inspeccion_semilla` (FK a `Unidad`)
- **Por qué:** cada empresa configura su unidad por defecto para inspecciones. Hoy es "semillas", pero mañana podría ser otra unidad. No se hardcodea en el código.

---

## 2. Formularios (`forms.py`)

#### `CamposInspeccionForm` (nuevo)
- Campos: `resultado`, `cant_semilla_mult_ha`, `um`, `responsable`
- Recibe `empresa` como kwarg → pre-selecciona `unidad_inspeccion_semilla` de la empresa
- **Por qué:** centraliza la validación del formulario de inspección

#### `VariedadPMGForm` (nuevo)
- Campos: solo `pmg`
- Modelo: `Variedad`
- Se muestra al editar un producto semilla
- **Por qué:** el usuario carga el PMG desde la pantalla de productos, no desde el admin

#### `ActividadInsumoForm`
- Eliminado `densidad_siembra` de los fields (ya no lo carga el usuario)
- **Por qué:** es redundante, se calcula automáticamente de dosis + PMG

#### `ConfiguracionEmpresaForm` (agro)
- Eliminado `pct_prima_semilla`
- Agregado `unidad_inspeccion_semilla`

---

## 3. Lógica de negocio (`funciones_aux.py`)

#### `validar_insumos()` — modificado
- Si el tipo es "siembra", valida que haya máximo **1 insumo con `categoria.es_semilla=True`**
- **Por qué:** no tiene sentido sembrar dos variedades distintas en una misma actividad de siembra

#### `validar_inspeccion()` — nuevo
- Verifica que el `inspeccion_form` sea válido cuando `tipo.requiere_inspeccion=True`

#### `guardar_inspeccion()` — nuevo
- Guarda `CamposInspeccion` vinculado a la actividad
- Retorna el objeto guardado

#### `guardar_cosecha()` — modificado
- Ahora retorna el objeto `CamposCosecha` para poder actualizarlo después del split

#### `registrar_actividad_aux()` — modificado
- Acepta parámetro `inspeccion_form`
- Llama a `validar_inspeccion()` y `guardar_inspeccion()` en el flujo

#### Auto-cálculo de `densidad_siembra` en `guardar_insumos_y_stock()`
```python
# Al guardar insumo de siembra con producto semilla:
densidad_siembra = dosis(kg/ha) × 1.000.000 / PMG(g)
```

#### Split de cosecha (paso 13b) — lógica central
Al registrar una cosecha, el sistema:
1. Busca la última inspección APROBADA del ciclo
2. Si existe, obtiene el PMG de la variedad sembrada (via insumo siembra → ProductoSemilla → Variedad)
3. Convierte semillas aprobadas/ha → kg según la unidad de inspección:
   - Si `um.requiere_pmg = True` → `kg_semilla = semillas × superficie × PMG / 1.000.000`
   - Si `um.requiere_pmg = False` → usa `ConversionUM` para convertir la unidad al kg base
4. Genera **dos** `MovimientoStock` ENTRADA:
   - Producto semilla certificada → `kg_semilla`
   - Producto grano consumo → `kg_consumo`
5. Actualiza `CamposCosecha.kg_semilla` y `CamposCosecha.kg_consumo`
6. Si no hay PMG cargado → todo va a consumo (sin error silencioso)
7. Si no hay inspección aprobada → todo va a consumo (comportamiento original)

---

## 4. Views (`views.py`)

#### `ajax_subtipos_tipo_actividad`
- Agrega `requiere_inspeccion` y `es_siembra` al JSON de respuesta
- **Por qué:** el frontend necesita saber si mostrar la sección de inspección y la columna `≈ sem/ha`

#### `ajax_productos_por_actividad`
- Agrega `es_semilla` y `pmg` al JSON de cada producto
- **Por qué:** el JS necesita saber si el producto seleccionado es semilla para mostrar el cálculo, y el PMG para calcularlo

#### `vista_agregar_actividad`
- Crea y valida `CamposInspeccionForm` con `empresa` para pre-seleccionar la unidad
- Pasa `inspeccion_form` al template y a `registrar_actividad_aux()`

#### `vista_editar_producto`
- Si el producto tiene `datos_semilla`, muestra `VariedadPMGForm` para editar el PMG de la variedad

#### `vista_lista_stock`
- Productos con `categoria.es_semilla=True` se incluyen en `lista_productos_finales` (tab "Stock de cosecha")
- **Por qué:** la semilla certificada es un producto final producido en la cosecha, no un insumo

#### `vista_detalle_ciclo`
- Prefetch agrega `camposcosecha` y `camposinspeccion__um`

---

## 5. Templates

#### `vista_agregar_actividad.html`
- Nueva sección **"Inspección de semilla"** (visible cuando `requiere_inspeccion=True`)
- Columna **"≈ sem/ha"** en tabla de insumos (visible solo en siembra para productos semilla)
- Cálculo JS en tiempo real: `dosis(kg) × 1.000.000 / PMG = semillas/ha`
- Tag `novalidate` en el form para evitar que campos ocultos bloqueen el submit

#### `vista_detalle_ciclo.html`
- En el detalle de cada actividad:
  - **Cosecha**: muestra rendimiento, kg semilla (verde), kg consumo
  - **Inspección**: badge APROBADO/RECHAZADO, semillas aprobadas/ha, responsable

#### `vista_lista_stock.html`
- Tab "Stock de cosecha": badges **Semilla** (amarillo) / **Consumo** (verde) por producto
- Tabla rediseñada con más padding y tipografía más limpia

#### `vista_producto.html`
- Sección "Datos de semilla" con campo PMG cuando el producto es semilla

#### `configuracion.html`
- Eliminada sección "Prima semilla"
- Nueva sección **"Semilla"** con selector de unidad de inspección por defecto

---

## 6. Migraciones aplicadas

| # | App | Nombre | Qué hace |
|---|---|---|---|
| 0026 | gestion_agro | inspeccion_semilla_cosecha | Crea CamposInspeccion, agrega kg_semilla/kg_consumo, densidad_siembra |
| 0027 | gestion_agro | requiere_inspeccion | Agrega requiere_inspeccion a TipoActividad |
| 0028 | gestion_agro | pmg_producto_semilla | Agregó pmg a ProductoSemilla (revertido en 0029) |
| 0029 | gestion_agro | pmg_a_variedad | Mueve pmg de ProductoSemilla → Variedad |
| 0007 | agro | unidad_inspeccion_semilla | Agrega unidad_inspeccion_semilla a Empresa |
| 0008 | agro | unidad_requiere_pmg | Agrega requiere_pmg a Unidad |

---

## 7. Configuración requerida (pasos manuales)

1. **Admin → Unidades**: crear unidad `Semillas` / abrev `sem` / `requiere_pmg = ✓`
2. **Configuración → Empresa**: seleccionar `Unidad inspección semilla = sem`
3. **Admin → Tipo actividad**: crear tipo `Inspección` con `requiere_inspeccion = ✓`
4. **Productos → editar cada producto semilla**: cargar el `PMG` de la variedad

---

## 8. Flujo completo

```
Siembra
  └─ ActividadInsumo (producto semilla, dosis kg/ha)
       └─ densidad_siembra = dosis × 1.000.000 / PMG  [auto]
       └─ ≈ sem/ha mostrado en el form [display only]

Inspección  (tipo.requiere_inspeccion = True)
  └─ CamposInspeccion
       ├─ resultado: APROBADO / RECHAZADO
       ├─ cant_semilla_mult_ha: semillas aprobadas por ha
       └─ um: unidad (default desde empresa, ej: sem)

Cosecha
  └─ CamposCosecha
       ├─ rendimiento (por ha)
       ├─ kg_semilla  [calculado]
       └─ kg_consumo  [calculado]
  └─ MovimientoStock ENTRADA → producto semilla certificada (kg_semilla)
  └─ MovimientoStock ENTRADA → producto grano consumo    (kg_consumo)
```
