# Manual: carga de catálogo (TipoActividad / SubTipoActividad / CategoriaProducto)

Guía para cargar a mano, vía Django admin, las filas de catálogo cuando una
migración no se puede correr todavía (ej: falta instalar una dependencia en
producción) o cuando se agrega un tipo/subtipo nuevo.

## 0. Antes de cargar nada en producción

Si el admin de `TipoActividad`/`SubTipoActividad`/`CategoriaProducto` muestra
un solo campo **"Nombre"** (sin separar en "Nombre [es]" / "Nombre [pt]"),
significa que el servidor todavía no tiene el paquete `django-modeltranslation`
instalado. Antes de cargar nada:

```bash
pip install -r requirements.txt
python manage.py migrate
```

Recién después de que `migrate` corra sin errores vas a ver el campo
"Nombre" partido en dos inputs por idioma.

## 1. TipoActividad

Campos clave: `Nombre [es]` / `Nombre [pt]`, `Tipo` (código de 1 letra,
libre, solo informativo — no se usa en ninguna lógica de negocio),
checkboxes (`Activo`, `Abre fase`, `Cierra fase`, `Requiere subtipo`,
`Requiere insumo`, `Requiere mo`, `Requiere maq`, `Requiere vist`,
`Requiere cosecha`, `Requer inspeção de semente` = `requiere_inspeccion`).

Catálogo actual (referencia):

| Nombre [es]    | Nombre [pt]    | Tipo |
|-----------------|-----------------|------|
| Siembra         | Plantio         | S    |
| Aplicación      | Aplicação       | A    |
| Fertilización   | Fertilização    | F    |
| Monitoreo       | Monitoramento   | M    |
| Cosecha         | Colheita        | C    |
| Inspeccion      | Inspeção        | M    |

Para un **TipoActividad de inspección** (como "Inspeccion"): marcar
`Activo` y `Requer inspeção de semente`. El resto de los checkboxes y horas
de mano de obra/máquina quedan en blanco/0.

## 2. SubTipoActividad

Cada subtipo pertenece a un `TipoActividad` (campo "Tipo actividad" en el
form). Campos clave: `Tipo actividad`, `Código`, `Nombre [es]` /
`Nombre [pt]`, `Activo`, `Abre fase`, `Cierra fase`.

### Bajo "Aplicación"

| Código | Nombre [es] | Nombre [pt] | Activo | Abre fase | Cierra fase |
|--------|-------------|-------------|--------|-----------|-------------|
| AH     | Herbicida   | Herbicida   | ✓      | —         | —           |
| AF     | Fungicida   | Fungicida   | ✓      | —         | —           |
| AI     | Insecticida | Insecticida | ✓      | —         | —           |
| AM     | Mixta       | Mista       | ✓      | —         | —           |
| AO     | Otras       | Outras      | ✓      | —         | —           |
| LP     | Limpa       | Limpa       | ✓      | ✓         | —           |

### Bajo "Siembra"

| Código | Nombre [es]       | Nombre [pt]       | Activo | Abre fase | Cierra fase |
|--------|-------------------|-------------------|--------|-----------|-------------|
| SP     | Cultivo Principal | Cultivo Principal | ✓      | ✓         | —           |
| SC     | Cobertura         | Cobertura         | ✓      | ✓         | —           |

## 3. CategoriaProducto

Campos clave: `Código`, `Nombre [es]` / `Nombre [pt]`, `Es semilla`.

| Código | Nombre [es]              | Nombre [pt]            | Es semilla |
|--------|--------------------------|--------------------------|------------|
| SEM    | Semilla                  | Semente                  | ✓          |
| FUN    | Fungicida                | Fungicida                | —          |
| HER    | Herbicida                | Herbicida                | —          |
| FER    | Fertilizante             | Fertilizante             | —          |
| INS    | Insecticida               | Insecticida               | —          |
| PF     | Producto Final           | Produto Final            | —          |
| PFS    | Producto Final - Semilla | Produto Final - Semente  | ✓          |

## 4. Verificación después de cargar

1. Cambiar el idioma del sitio a portugués y confirmar que los nombres
   cargados se ven traducidos en: dropdowns de actividad, AJAX de subtipos,
   `vista_detalle_ciclo.html`, `vista_parametros_actividades.html`,
   `vista_lista_stock.html`.
2. Confirmar que los íconos por tipo de actividad en
   `vista_detalle_ciclo.html` siguen apareciendo bien en ambos idiomas.
3. Registrar una actividad de prueba con la UI en portugués y confirmar que
   las validaciones de negocio (siembra única, cobertura/cultivo principal
   excluyentes, orden siembra→cosecha) siguen funcionando igual que en
   español.

## Nota técnica

El campo `nombre` que se ve en templates/listas sigue funcionando solo
(resuelve el idioma activo del usuario automáticamente). Las comparaciones
de lógica de negocio en el código (`funciones_aux.py`, `views.py`,
`vista_detalle_ciclo.html`) usan `nombre_es` específicamente para no
depender del idioma activo — por eso es importante completar siempre el
campo `Nombre [es]` con el valor correcto en español, igual que en esta
tabla.
