"""
Seed de productos para Agroinnova — agroquímicos, fertilizantes y semillas
típicos del Alto Uruguai / Campos Novos (SC/RS), Brasil.
"""
from django.core.management.base import BaseCommand


CATEGORIAS = [
    ("AGROQUIMICO",  "Agroquímico",     False),
    ("FERTILIZANTE", "Fertilizante",    False),
    ("SEMILLA",      "Semilla",         True),
    ("ADJUVANTE",    "Adjuvante",       False),
    ("INSUMO",       "Insumo geral",    False),
    ("PRODUTO_FINAL","Produto final",   False),
]

# (codigo, nombre, categoria_codigo, unidad_base_abr, activo)
PRODUCTOS = [
    # ── Herbicidas ──────────────────────────────────────────────────────
    ("HRB-001", "Glifosato 480 SL",            "AGROQUIMICO",  "L",   True),
    ("HRB-002", "Glufosinato Glucare BLD 20",   "AGROQUIMICO",  "L",   True),
    ("HRB-003", "2,4-D Amina 806 SL",           "AGROQUIMICO",  "L",   True),
    ("HRB-004", "Dicamba 480 SL",               "AGROQUIMICO",  "L",   True),
    ("HRB-005", "Clethodim 240 EC",             "AGROQUIMICO",  "L",   True),
    # ── Fungicidas ──────────────────────────────────────────────────────
    ("FNG-001", "Azoxistrobina + Ciproconazol", "AGROQUIMICO",  "L",   True),
    ("FNG-002", "Tebuconazol 200 EC",           "AGROQUIMICO",  "L",   True),
    ("FNG-003", "Piraclostrobina + Epoxiconazol","AGROQUIMICO", "L",   True),
    ("FNG-004", "Mancozeb 800 WP",              "AGROQUIMICO",  "kg",  True),
    # ── Inseticidas ─────────────────────────────────────────────────────
    ("INS-001", "Imidacloprida 700 WG",         "AGROQUIMICO",  "kg",  True),
    ("INS-002", "Lambda-cialotrina 50 EC",      "AGROQUIMICO",  "L",   True),
    ("INS-003", "Tiametoxam 250 WG",            "AGROQUIMICO",  "kg",  True),
    # ── Adjuvantes ──────────────────────────────────────────────────────
    ("ADJ-001", "Óleo Mineral Agefix BD 20 LT", "ADJUVANTE",   "L",   True),
    ("ADJ-001B","Óleo Vegetal Assist",           "ADJUVANTE",   "L",   True),
    # ── Fertilizantes ───────────────────────────────────────────────────
    ("FRT-001", "Fertilizante NPK 02-20-20",    "FERTILIZANTE", "kg",  True),
    ("FRT-002", "Fertilizante NPK 05-20-20",    "FERTILIZANTE", "kg",  True),
    ("FRT-003", "Ureia 45% N",                  "FERTILIZANTE", "kg",  True),
    ("FRT-004", "KCl 60% K2O",                  "FERTILIZANTE", "kg",  True),
    ("FRT-005", "Superfosfato Simples",          "FERTILIZANTE", "kg",  True),
    ("FRT-006", "Gesso Agrícola",               "FERTILIZANTE", "kg",  True),
    ("FRT-007", "Calcário Dolomítico PRNT 85",  "FERTILIZANTE", "kg",  True),
    # ── Semillas ────────────────────────────────────────────────────────
    ("SEM-SOJ-1","Semente Soja TMG 7062 IPRO",  "SEMILLA",      "kg",  True),
    ("SEM-SOJ-2","Semente Soja NA 5909 RG",     "SEMILLA",      "kg",  True),
    ("SEM-MIL-1","Semente Milho P4285H",        "SEMILLA",      "kg",  True),
    ("SEM-TRI-1","Semente Trigo Ametista",      "SEMILLA",      "kg",  True),
    ("SEM-CAR-1","Semente Carinata Joule",      "SEMILLA",      "kg",  True),
    # ── Insumos generales ───────────────────────────────────────────────
    ("INS-GER-1","Inoculante Bradyrhizobium",   "INSUMO",       "L",   True),
    ("INS-GER-2","Micronutrientes Boro + Zinco","INSUMO",       "kg",  True),
]

# (codigo_producto, nombre_presentacion, unidad_factura_str, contenido, unidad_contenido_abr)
PRESENTACIONES = [
    # Herbicidas líquidos
    ("HRB-001", "Galão 5L",      "gl",   5.0,    "L"),
    ("HRB-001", "Balde 20L",     "bld",  20.0,   "L"),
    ("HRB-002", "Balde 20L",     "bld",  20.0,   "L"),
    ("HRB-003", "Galão 5L",      "gl",   5.0,    "L"),
    ("HRB-003", "Balde 20L",     "bld",  20.0,   "L"),
    ("HRB-004", "Frasco 1L",     "un",   1.0,    "L"),
    ("HRB-004", "Galão 5L",      "gl",   5.0,    "L"),
    ("HRB-005", "Frasco 1L",     "un",   1.0,    "L"),
    # Fungicidas
    ("FNG-001", "Frasco 1L",     "un",   1.0,    "L"),
    ("FNG-001", "Galão 5L",      "gl",   5.0,    "L"),
    ("FNG-002", "Frasco 1L",     "un",   1.0,    "L"),
    ("FNG-003", "Frasco 1L",     "un",   1.0,    "L"),
    ("FNG-004", "Saco 1kg",      "sc",   1.0,    "kg"),
    # Inseticidas
    ("INS-001", "Embalagem 1kg", "un",   1.0,    "kg"),
    ("INS-002", "Frasco 1L",     "un",   1.0,    "L"),
    ("INS-003", "Embalagem 1kg", "un",   1.0,    "kg"),
    # Adjuvantes
    ("ADJ-001", "Balde 20L",     "bld",  20.0,   "L"),
    ("ADJ-001B","Frasco 1L",     "un",   1.0,    "L"),
    # Fertilizantes
    ("FRT-001", "Saco 50kg",     "sc",   50.0,   "kg"),
    ("FRT-001", "Bigbag 1000kg", "un",   1000.0, "kg"),
    ("FRT-002", "Saco 50kg",     "sc",   50.0,   "kg"),
    ("FRT-003", "Saco 50kg",     "sc",   50.0,   "kg"),
    ("FRT-004", "Saco 50kg",     "sc",   50.0,   "kg"),
    ("FRT-005", "Saco 50kg",     "sc",   50.0,   "kg"),
    ("FRT-006", "Saco 50kg",     "sc",   50.0,   "kg"),
    ("FRT-007", "Saco 50kg",     "sc",   50.0,   "kg"),
    # Semillas
    ("SEM-SOJ-1","Saco 40kg",   "sc",   40.0,   "kg"),
    ("SEM-SOJ-2","Saco 40kg",   "sc",   40.0,   "kg"),
    ("SEM-MIL-1","Saco 20kg",   "sc",   20.0,   "kg"),
    ("SEM-TRI-1","Saco 50kg",   "sc",   50.0,   "kg"),
    ("SEM-CAR-1","Saco 25kg",   "sc",   25.0,   "kg"),
    # Insumos
    ("INS-GER-1","Frasco 1L",   "un",   1.0,    "L"),
    ("INS-GER-2","Embalagem 1kg","un",  1.0,    "kg"),
]


class Command(BaseCommand):
    help = "Carga categorías, productos y presentaciones para Agroinnova"

    def add_arguments(self, parser):
        parser.add_argument("--empresa", type=str, default="Agroinnova")

    def handle(self, *args, **options):
        from agro.models import Empresa, Unidad
        from gestion_agro.models import CategoriaProducto, Producto, PresentacionProducto

        try:
            empresa = Empresa.objects.get(nombre=options["empresa"])
        except Empresa.DoesNotExist:
            self.stderr.write(f"Empresa '{options['empresa']}' no encontrada.")
            return

        # Categorías
        cats = {}
        for codigo, nombre, es_semilla in CATEGORIAS:
            c, created = CategoriaProducto.objects.get_or_create(
                codigo=codigo,
                defaults={"nombre": nombre, "es_semilla": es_semilla},
            )
            cats[codigo] = c
            if created:
                self.stdout.write(f"  Categoría: {nombre}")

        # Unidades
        unidades = {u.abreviatura: u for u in Unidad.objects.all()}

        # Productos
        prods = {}
        for codigo, nombre, cat_cod, unid_abr, activo in PRODUCTOS:
            unidad = unidades.get(unid_abr)
            if not unidad:
                self.stdout.write(self.style.WARNING(f"  SKIP {codigo}: unidad '{unid_abr}' no existe"))
                continue
            p, created = Producto.objects.get_or_create(
                empresa=empresa,
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "categoria": cats[cat_cod],
                    "unidad_base": unidad,
                    "activo": activo,
                    "maneja_stock": True,
                    "producto_final": cat_cod == "PRODUTO_FINAL",
                },
            )
            prods[codigo] = p
            if created:
                self.stdout.write(f"  Producto: {nombre}")

        # Presentaciones
        for cod_prod, nombre_pres, unid_fact, contenido, unid_cont_abr in PRESENTACIONES:
            p = prods.get(cod_prod)
            if not p:
                continue
            unidad_cont = unidades.get(unid_cont_abr)
            if not unidad_cont:
                continue
            _, created = PresentacionProducto.objects.get_or_create(
                producto=p,
                nombre=nombre_pres,
                defaults={
                    "unidad_factura":   unid_fact,
                    "contenido":        contenido,
                    "unidad_contenido": unidad_cont,
                },
            )
            if created:
                self.stdout.write(f"    Presentación: {cod_prod} — {nombre_pres}")

        self.stdout.write(self.style.SUCCESS("Seed de productos completado."))
