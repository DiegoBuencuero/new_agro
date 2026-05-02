# seed.py
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from agro.models import Unidad, ConversionUM, Empresa, Pais, Provincia, Ciudad
from gestion_agro.models import (
    CategoriaProducto, Producto, Cultivo,
    TipoActividad, SubTipoActividad, TipoActividadCategoriaProducto,
    Deposito
)

# ─── EMPRESA ──────────────────────────────────────────────────────
empresa = Empresa.objects.get(nombre="Agroinnova")
print(f"Empresa: {empresa}")

# ─── GEOGRAFIA ────────────────────────────────────────────────────
print("\n=== GEOGRAFIA ===")
pais, c = Pais.objects.get_or_create(nombre="Brasil")
print(f"  {'✓' if c else '-'} {pais}")
provincia, c = Provincia.objects.get_or_create(nombre="Santa Catarina", pais=pais)
print(f"  {'✓' if c else '-'} {provincia}")
ciudad, c = Ciudad.objects.get_or_create(nombre="Campos Novos", provincia=provincia)
print(f"  {'✓' if c else '-'} {ciudad}")

# ─── UNIDADES ─────────────────────────────────────────────────────
print("\n=== UNIDADES ===")
unidades = [
    {"nombre": "Kilogramo", "abreviatura": "kg",  "factor_a_base": 1},
    {"nombre": "Tonelada",  "abreviatura": "tn",  "factor_a_base": 1000},
    {"nombre": "Quintal",   "abreviatura": "qq",  "factor_a_base": 100},
    {"nombre": "Litro",     "abreviatura": "L",   "factor_a_base": 1},
    {"nombre": "Mililitro", "abreviatura": "ml",  "factor_a_base": 0.001},
    {"nombre": "Hectárea",  "abreviatura": "ha",  "factor_a_base": 1},
    {"nombre": "Unidad",    "abreviatura": "und", "factor_a_base": 1},
    {"nombre": "Gramo",     "abreviatura": "g",   "factor_a_base": 0.001},
]
um_objs = {}
for u in unidades:
    obj, c = Unidad.objects.get_or_create(
        abreviatura=u["abreviatura"],
        defaults={"nombre": u["nombre"], "factor_a_base": u["factor_a_base"]}
    )
    um_objs[u["abreviatura"]] = obj
    print(f"  {'✓' if c else '-'} {obj}")

# ─── CONVERSIONES ─────────────────────────────────────────────────
print("\n=== CONVERSIONES ===")
conversiones = [
    ("tn", "kg", 1000),
    ("qq", "kg", 100),
    ("g",  "kg", 0.001),
    ("ml", "L",  0.001),
]
for origen, destino, factor in conversiones:
    obj, c = ConversionUM.objects.get_or_create(
        um_origen=um_objs[origen],
        um_destino=um_objs[destino],
        defaults={"factor": factor}
    )
    print(f"  {'✓' if c else '-'} {obj}")

# ─── CATEGORIAS ───────────────────────────────────────────────────
print("\n=== CATEGORIAS PRODUCTO ===")
categorias = [
    {"codigo": "SEM", "nombre": "Semilla",       "es_semilla": True},
    {"codigo": "FUN", "nombre": "Fungicida",      "es_semilla": False},
    {"codigo": "HER", "nombre": "Herbicida",      "es_semilla": False},
    {"codigo": "FER", "nombre": "Fertilizante",   "es_semilla": False},
    {"codigo": "INS", "nombre": "Insecticida",    "es_semilla": False},
    {"codigo": "PF",  "nombre": "Producto Final", "es_semilla": False},
]
cat_objs = {}
for c_data in categorias:
    obj, c = CategoriaProducto.objects.get_or_create(
        codigo=c_data["codigo"],
        defaults={"nombre": c_data["nombre"], "es_semilla": c_data["es_semilla"]}
    )
    cat_objs[c_data["codigo"]] = obj
    print(f"  {'✓' if c else '-'} {obj}")

# ─── DEPOSITOS ────────────────────────────────────────────────────
print("\n=== DEPOSITOS ===")
dep_objs = {}
for d in [{"nombre": "Depósito Principal", "tipo": "PROPIO"}, {"nombre": "Cooperativa", "tipo": "EXTERNO"}]:
    obj, c = Deposito.objects.get_or_create(
        empresa=empresa, nombre=d["nombre"],
        defaults={"tipo": d["tipo"], "ciudad": ciudad}
    )
    dep_objs[d["nombre"]] = obj
    print(f"  {'✓' if c else '-'} {obj}")

# ─── PRODUCTOS FINALES ────────────────────────────────────────────
print("\n=== PRODUCTOS FINALES ===")
pf_objs = {}
for p in [
    {"codigo": "PF-SOJA",  "nombre": "Soja grano"},
    {"codigo": "PF-MAIZ",  "nombre": "Maíz grano"},
    {"codigo": "PF-TRIGO", "nombre": "Trigo grano"},
]:
    obj, c = Producto.objects.get_or_create(
        empresa=empresa, codigo=p["codigo"],
        defaults={
            "nombre": p["nombre"],
            "categoria": cat_objs["PF"],
            "unidad_base": um_objs["kg"],
            "precio": 0,
            "maneja_stock": True,
            "activo": True,
            "producto_final": True,
            "deposito_default": dep_objs["Depósito Principal"],
        }
    )
    pf_objs[p["codigo"]] = obj
    print(f"  {'✓' if c else '-'} {obj}")

# ─── CULTIVOS ─────────────────────────────────────────────────────
print("\n=== CULTIVOS ===")
cultivo_objs = {}
for c_data in [
    {"nombre": "Soja",  "pf": "PF-SOJA"},
    {"nombre": "Maíz",  "pf": "PF-MAIZ"},
    {"nombre": "Trigo", "pf": "PF-TRIGO"},
]:
    obj, c = Cultivo.objects.get_or_create(
        empresa=empresa, nombre=c_data["nombre"],
        defaults={"producto_default": pf_objs[c_data["pf"]]}
    )
    if not c and not obj.producto_default:
        obj.producto_default = pf_objs[c_data["pf"]]
        obj.save()
    obj.productos_finales.add(pf_objs[c_data["pf"]])
    cultivo_objs[c_data["nombre"]] = obj
    print(f"  {'✓' if c else '-'} {obj}")

# ─── TIPOS DE ACTIVIDAD ───────────────────────────────────────────
print("\n=== TIPOS DE ACTIVIDAD ===")
tipos_data = [
    {"nombre": "Siembra",       "tipo": "S", "abre_fase": True,  "cierra_fase": False, "requiere_insumo": True,  "requiere_mo": True,  "requiere_maq": True,  "requiere_cosecha": False, "requiere_vist": False},
    {"nombre": "Aplicación",    "tipo": "A", "abre_fase": False, "cierra_fase": False, "requiere_insumo": True,  "requiere_mo": True,  "requiere_maq": True,  "requiere_cosecha": False, "requiere_vist": False},
    {"nombre": "Fertilización", "tipo": "F", "abre_fase": False, "cierra_fase": False, "requiere_insumo": True,  "requiere_mo": True,  "requiere_maq": True,  "requiere_cosecha": False, "requiere_vist": False},
    {"nombre": "Monitoreo",     "tipo": "M", "abre_fase": False, "cierra_fase": False, "requiere_insumo": False, "requiere_mo": False, "requiere_maq": False, "requiere_cosecha": False, "requiere_vist": True},
    {"nombre": "Cosecha",       "tipo": "C", "abre_fase": False, "cierra_fase": True,  "requiere_insumo": False, "requiere_mo": True,  "requiere_maq": True,  "requiere_cosecha": True,  "requiere_vist": False},
]
tipo_objs = {}
for t in tipos_data:
    obj, c = TipoActividad.objects.get_or_create(
        nombre=t["nombre"],
        defaults={
            "tipo": t["tipo"], "activo": True,
            "abre_fase": t["abre_fase"], "cierra_fase": t["cierra_fase"],
            "requiere_insumo": t["requiere_insumo"], "requiere_mo": t["requiere_mo"],
            "requiere_maq": t["requiere_maq"], "requiere_cosecha": t["requiere_cosecha"],
            "requiere_vist": t["requiere_vist"],
        }
    )
    tipo_objs[t["nombre"]] = obj
    print(f"  {'✓' if c else '-'} {obj}")

# ─── SUBTIPOS ─────────────────────────────────────────────────────
print("\n=== SUBTIPOS DE ACTIVIDAD ===")
subtipos_data = [
    {"tipo": "Siembra",       "codigo": "SC", "nombre": "Cobertura",        "abre_fase": True,  "cierra_fase": False},
    {"tipo": "Siembra",       "codigo": "SP", "nombre": "Cultivo Principal", "abre_fase": True,  "cierra_fase": False},
    {"tipo": "Aplicación",    "codigo": "AH", "nombre": "Herbicida",         "abre_fase": False, "cierra_fase": False},
    {"tipo": "Aplicación",    "codigo": "AF", "nombre": "Fungicida",         "abre_fase": False, "cierra_fase": False},
    {"tipo": "Aplicación",    "codigo": "AI", "nombre": "Insecticida",       "abre_fase": False, "cierra_fase": False},
    {"tipo": "Aplicación",    "codigo": "AM", "nombre": "Mixta",             "abre_fase": False, "cierra_fase": False},
    {"tipo": "Aplicación",    "codigo": "AO", "nombre": "Otras",             "abre_fase": False, "cierra_fase": False},
    {"tipo": "Fertilización", "codigo": "FC", "nombre": "Cobertura",         "abre_fase": False, "cierra_fase": False},
    {"tipo": "Fertilización", "codigo": "FB", "nombre": "Base",              "abre_fase": False, "cierra_fase": False},
    {"tipo": "Fertilización", "codigo": "FO", "nombre": "Otras",             "abre_fase": False, "cierra_fase": False},
]
subtipo_objs = {}
for s in subtipos_data:
    obj, c = SubTipoActividad.objects.get_or_create(
        tipo_actividad=tipo_objs[s["tipo"]],
        codigo=s["codigo"],
        defaults={
            "nombre": s["nombre"], "activo": True,
            "abre_fase": s["abre_fase"], "cierra_fase": s["cierra_fase"],
        }
    )
    subtipo_objs[s["codigo"]] = obj
    print(f"  {'✓' if c else '-'} {s['tipo']} → {obj}")

# ─── TIPO ACTIVIDAD → CATEGORIA ───────────────────────────────────
print("\n=== TIPO ACTIVIDAD → CATEGORIA ===")
relaciones = [
    ("Siembra",       None, "SEM"),
    ("Siembra",       "SC", "SEM"),
    ("Siembra",       "SP", "SEM"),
    ("Aplicación",    None, "HER"),
    ("Aplicación",    "AH", "HER"),
    ("Aplicación",    "AF", "FUN"),
    ("Aplicación",    "AI", "INS"),
    ("Aplicación",    "AM", "HER"),
    ("Aplicación",    "AM", "FUN"),
    ("Aplicación",    "AM", "INS"),
    ("Aplicación",    "AO", "HER"),
    ("Aplicación",    "AO", "FUN"),
    ("Aplicación",    "AO", "INS"),
    ("Fertilización", None, "FER"),
    ("Fertilización", "FC", "FER"),
    ("Fertilización", "FB", "FER"),
    ("Fertilización", "FO", "FER"),
]
for tipo_nombre, subtipo_codigo, cat_codigo in relaciones:
    subtipo = subtipo_objs.get(subtipo_codigo) if subtipo_codigo else None
    obj, c = TipoActividadCategoriaProducto.objects.get_or_create(
        tipo_actividad=tipo_objs[tipo_nombre],
        subtipo_actividad=subtipo,
        categoria_producto=cat_objs[cat_codigo],
        defaults={"activo": True}
    )
    label = f"{tipo_nombre}/{subtipo_codigo}" if subtipo_codigo else tipo_nombre
    print(f"  {'✓' if c else '-'} {label} → {cat_codigo}")

# ─── EMPRESA DEFAULTS ─────────────────────────────────────────────
print("\n=== EMPRESA DEFAULTS ===")
empresa.deposito_insumos_default = dep_objs["Depósito Principal"]
empresa.deposito_producto_final_default = dep_objs["Depósito Principal"]
empresa.save()
print(f"  ✓ insumos default: {empresa.deposito_insumos_default}")
print(f"  ✓ producto final default: {empresa.deposito_producto_final_default}")

print("\n=== SEED COMPLETO ===")