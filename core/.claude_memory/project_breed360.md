---
name: project-breed360
description: "Sistema ganadero bovino Django — estructura, modelos, flujos reproductivos y stack técnico"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6820c48f-6a47-48c1-a11c-72d2eb8f08f2
---

## Qué es
**breed360** — sistema de gestión ganadera bovina desarrollado en Django.
- Ruta local: `/home/diego/Work/Django/breed360/core/`
- Desplegado en: `innobreed.pythonanywhere.com`
- Stack: Django 6.0.3, SQLite, Pillow 12.1.1, i18n ES/PT

**Why:** Plataforma para cabañas y establecimientos ganaderos que necesitan trazabilidad reproductiva, sanitaria y productiva de animales bovinos. Apunta a Argentina (SENASA, Breedplan).

## Apps
### `agro` — infraestructura base
Modelos: `Profile` (extiende User con empresa/perfil), `Empresa`, `Moneda`, `Proveedor`, `Unidad`, `ConversionUM`, geografía (`Pais`, `Provincia`, `Ciudad`).

### `gestion_bovinos` — núcleo ganadero
Toda la lógica de animales, reproductiva, sanitaria y de grupos.

## Jerarquía de datos
```
Empresa
  └─ Establecimiento (tiene SENASA zona+estab y código Breedplan)
       └─ Rodeo (agrupamiento físico de animales por tipo)
            └─ AnimalBovino
```

Cada usuario tiene un `Profile.empresa` que filtra todo el sistema.

## Modelos clave en gestion_bovinos

### AnimalBovino
- Identificado por tatuaje (`AA01`), caravana SENASA (`ZZ-A001`), o Breedplan
- Campos: sexo, fecha_nacimiento, raza, subraza, madre (FK self), padre_genetico
- Categoría actual con historial de transiciones validadas (`TransicionCategoriaPermitida`)
- Estado reproductivo, estado de vida, destino productivo
- Auto-asigna `numero_nacimiento` y código SENASA al crear
- Properties: `edad_dias`, `edad_display`, `ultimo_peso`, `peso_estimado_hoy` (usa GDP configurado por establecimiento)

### GrupoServicio — grupos de servicio reproductivo
- Tipos: `INSEMINACION` (IATF/IA), `SERVICIO_NATURAL`, `REPASO`
- Estado: PLANIFICADO → EN_CURSO → CERRADO/CANCELADO
- Tiene filtros automáticos al cargar animales: días mínimos posparto, excluir preñadas, edad/peso mínimo
- Métodos: `agregar_animal()`, `quitar_animal()`, `cerrar()`

### MiembroGrupoServicio
- Historial de membresía: una vaca puede entrar y salir del mismo grupo varias veces
- Constraint: solo un ingreso activo por animal por grupo a la vez
- MotivoEgreso: CAMBIO_LOTE, DESCARTE, PRENADA, VACIA, MUERTE, ERROR_CARGA, OTRO

### EventoGrupoServicio
- Eventos del protocolo sobre el grupo completo (sincronización, retiro, IA, etc.)
- Si `TipoEvento.crea_evento_reproductivo=True` → crea `EventoReproductivo` por cada vaca miembro
- Soporta insumo + dosis + vía de administración
- Genera `AplicacionInsumoAnimal` por animal para trazabilidad individual

### EventoReproductivo
- Registro individual por vaca: servicio → tacto → parto
- `crear_ternero()`: crea `AnimalBovino` + `MovimientoRodeo` + `HistorialCategoriaAnimal` en una transacción
- Al guardar: si `es_efectivo=True` desmarca otros eventos efectivos de la misma madre

### DiagnosticoPreñezRodeo + ResultadoDiagnosticoAnimal
- Sesión de tacto/ecografía sobre un grupo o manejo reproductivo
- Signal `actualizar_estado_reproductivo_por_diagnostico`:
  - Actualiza `animal.estado_reproductivo`
  - Sincroniza `resultado_tacto` en el `EventoReproductivo` activo
  - Si vacía Y tiene grupo → egreso automático del grupo

### Catálogos (todos heredan BaseCatalogo)
`TipoRodeo`, `EstadoVidaAnimal`, `CategoriaBovino`, `EstadoReproductivo`, `DestinoProductivoBovino`, `TipoMedicion`, `RazaBovino`, `SubRaza`, `Insumo`, `TipoEvento`

### Otros modelos
- `ManejoReproductivo`: ciclo reproductivo completo de un rodeo por temporada (agrupa grupos)
- `MovimientoRodeo`: trazabilidad de cambio de rodeo (signal actualiza `animal.rodeo`)
- `PadreGenetico`: toros/padres con código, raza, proveedor; puede vincularse a `AnimalBovino` interno
- `MedicionAnimal`: pesadas, ecografías (AOB, GIM, GD, GC), circunferencia escrotal
- `RegistroSanitario`: vacunas, tratamientos, desparasitaciones con refuerzo programado
- `ConfigGDPEstablecimiento`: GDP (ganancia diaria de peso) por sexo, usado en `peso_estimado_hoy`
- `UmbralCambioCategoria` + Signal `evaluar_cambio_categoria`: al registrar pesada, genera `SugerenciaCambioCategoria` si el animal cumple condiciones

## URLs principales
```
/                          → index (dashboard)
/establecimientos/         → lista y CRUD
/grupos/                   → crear/editar/detalle GrupoServicio
/grupos/<pk>/diagnostico/  → diagnóstico de preñez del grupo
/bovinos/                  → lista, crear, editar, detalle, mover
/eventos-reproductivos/    → lista, crear, detalle, crear-ternero
/ajax/...                  → endpoints AJAX (rodeos, animales, agregar miembros, eventos)
```

## Flujo reproductivo típico (IATF)
1. Crear `GrupoServicio` (tipo INSEMINACION, con padre genético)
2. Cargar vacas desde el rodeo (con filtros automáticos)
3. Registrar `EventoGrupoServicio` por cada paso del protocolo (D0 hormona, D8 retiro, D10 IA)
4. El evento de IA crea `EventoReproductivo` por cada vaca activa en el grupo
5. Después de ~30 días: crear `DiagnosticoPreñezRodeo` → registrar resultados individuales
6. Vacías: egresan automáticamente del grupo; preñadas: estado actualizado
7. Al parto: `EventoReproductivo.crear_ternero()` da de alta el ternero

## Notas técnicas
- Multi-tenant por `Empresa` (vía `Profile.empresa`); superadmin ve todo
- `ControlModel` (abstracto): agrega `created_at` / `updated_at` a casi todo
- `BaseCatalogo` (abstracto): nombre único, código, activo, orden — base de catálogos
- Identificación SENASA: `ZZ-A001` donde ZZ = prefijo establecimiento, A = prefijo animal, 001 = número
- Login en `/login/`, redirige a `/` tras autenticarse; usa `django.contrib.auth.urls`

## Feedback de dominio — cliente Mailen Liti (veterinaria, 2026-04-13/15)

### Mediciones vs Controles
- **Todo es "Mediciones"** conceptualmente. El término "Controles" aplica más específico a feedlot: seguimiento de ganancia/engorde diario (GDP).
- Acción: revisar si la nomenclatura en el sistema refleja esto (renombrar si hace falta).

### Lógica de categorías (confirmado por Mailen)
La clasificación depende principalmente de **edad**, pero también de **peso** y **estado reproductivo** (hembras).

Trayectorias confirmadas:
- **Hembras:** Ternera → Vaquillona → Vaca
- **Machos castrados:** Ternero → Novillito → Novillo
- **Machos enteros:** Ternero → Torito → Toro

Criterios por categoría (rangos exactos pendientes — Mailen los va a pasar):
- Ternero/a: desde nacimiento hasta X meses / X kg
- El paso a Novillo requiere castración
- El paso a Vaca requiere al menos un parto (estado reproductivo)
- El paso a Toro puede depender de edad o de uso como reproductor

**How to apply:** Cuando se implemente la automatización de categorías, usar estas tres trayectorias. Los rangos exactos (edad en meses, peso en kg) deben cargarse como `UmbralCambioCategoria` una vez que Mailen los confirme. La condición de castración y parto son eventos discretos, no umbrales numéricos.

**How to apply:** Cuando el usuario pida agregar funcionalidad o corregir algo, este contexto permite entender la jerarquía completa y los efectos secundarios de los signals antes de tocar el código.
