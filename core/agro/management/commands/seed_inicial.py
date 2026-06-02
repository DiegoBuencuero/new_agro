from django.core.management.base import BaseCommand
from agro.models import Moneda, Pais, Provincia, Ciudad, Unidad, ConversionUM
from gestion_agro.models import Cultivo, CategoriaProducto


UNIDADES = [
    # (nombre, abreviatura, factor_a_base_kg, requiere_pmg)
    ("Kilogramo",  "kg",    1.0,       False),
    ("Gramo",      "g",     0.001,     False),
    ("Tonelada",   "tn",    1000.0,    False),
    ("Saca",       "sc",    60.0,      False),  # 1 saca = 60 kg (estándar BR)
    ("Litro",      "L",     1.0,       False),  # masa ≈ densidad variable; factor neutro
    ("Mililitro",  "mL",    0.001,     False),
    ("Semilla",    "sem",   1.0,       True),   # requiere PMG
]

# Conversiones explícitas entre unidades de masa (base = kg)
# (origen_abr, destino_abr, factor)  →  origen * factor = destino
CONVERSIONES = [
    ("kg",  "g",   1000.0),
    ("kg",  "tn",  0.001),
    ("kg",  "sc",  1/60),
    ("g",   "kg",  0.001),
    ("g",   "tn",  0.000001),
    ("tn",  "kg",  1000.0),
    ("tn",  "g",   1000000.0),
    ("tn",  "sc",  1000/60),
    ("sc",  "kg",  60.0),
    ("sc",  "tn",  0.06),
    ("L",   "mL",  1000.0),
    ("mL",  "L",   0.001),
]

PAISES_PROVINCIAS_CIUDADES = {
    "Brasil": {
        "Mato Grosso do Sul": ["Campo Grande", "Dourados", "Três Lagoas", "Corumbá", "Ponta Porã"],
        "Mato Grosso":        ["Cuiabá", "Sinop", "Rondonópolis", "Tangará da Serra"],
        "Paraná":             ["Curitiba", "Londrina", "Maringá", "Cascavel", "Pato Branco"],
        "São Paulo":          ["São Paulo", "Campinas", "Ribeirão Preto", "Bauru"],
        "Rio Grande do Sul":  ["Porto Alegre", "Pelotas", "Santa Maria", "Caxias do Sul"],
        "Goiás":              ["Goiânia", "Anápolis", "Rio Verde", "Jataí"],
        "Minas Gerais":       ["Belo Horizonte", "Uberlândia", "Uberaba", "Patos de Minas"],
    },
    "Argentina": {
        "Buenos Aires":   ["Buenos Aires", "La Plata", "Mar del Plata", "Bahía Blanca", "Tandil"],
        "Córdoba":        ["Córdoba", "Río Cuarto", "Villa María", "San Francisco"],
        "Santa Fe":       ["Rosario", "Santa Fe", "Rafaela", "Venado Tuerto"],
        "Entre Ríos":     ["Paraná", "Concordia", "Gualeguaychú"],
        "Chaco":          ["Resistencia", "Presidencia Roque Sáenz Peña"],
    },
    "Paraguay": {
        "Central":    ["Asunción", "Luque", "San Lorenzo", "Fernando de la Mora"],
        "Alto Paraná":["Ciudad del Este", "Hernandarias", "Minga Guazú"],
        "Itapúa":     ["Encarnación", "Coronel Bogado"],
    },
}

MONEDAS = [
    ("Real brasileño",   "BRL"),
    ("Dólar",            "USD"),
    ("Peso argentino",   "ARS"),
    ("Guaraní paraguayo","PYG"),
]

CULTIVOS = ["Soja", "Milho", "Trigo", "Girassol", "Feijão", "Carinata"]

CATEGORIAS_PRODUCTO = [
    # (codigo, nombre, es_semilla)
    ("PRODUCTO_FINAL", "Producto final",  False),
    ("INSUMO",         "Insumo",          False),
    ("SEMILLA",        "Semilla",         True),
    ("FERTILIZANTE",   "Fertilizante",    False),
    ("AGROQUIMICO",    "Agroquímico",     False),
    ("COMBUSTIBLE",    "Combustible",     False),
    ("OTROS",          "Otros",           False),
]


class Command(BaseCommand):
    help = "Carga datos iniciales: monedas, unidades, conversiones y ciudades BR/AR/PY"

    def add_arguments(self, parser):
        parser.add_argument("--empresa", type=str, default=None)

    def handle(self, *args, **options):
        self._seed_monedas()
        self._seed_unidades()
        self._seed_conversiones()
        self._seed_categorias()
        self._seed_geografico()
        if options["empresa"]:
            self._seed_cultivos(options["empresa"])
        self.stdout.write(self.style.SUCCESS("Seed inicial completado."))

    def _seed_monedas(self):
        for nombre, corto in MONEDAS:
            obj, created = Moneda.objects.get_or_create(corto=corto, defaults={"nombre": nombre})
            if created:
                self.stdout.write(f"  Moneda creada: {obj}")

    def _seed_unidades(self):
        self._unidades = {}
        for nombre, abr, factor, pmg in UNIDADES:
            obj, created = Unidad.objects.get_or_create(
                abreviatura=abr,
                defaults={"nombre": nombre, "factor_a_base": factor, "requiere_pmg": pmg},
            )
            self._unidades[abr] = obj
            if created:
                self.stdout.write(f"  Unidad creada: {obj}")

    def _seed_conversiones(self):
        for orig_abr, dest_abr, factor in CONVERSIONES:
            orig = self._unidades.get(orig_abr)
            dest = self._unidades.get(dest_abr)
            if not orig or not dest:
                continue
            obj, created = ConversionUM.objects.get_or_create(
                um_origen=orig, um_destino=dest,
                defaults={"factor": factor},
            )
            if created:
                self.stdout.write(f"  Conversión creada: {orig_abr} → {dest_abr} (x{factor})")

    def _seed_categorias(self):
        for codigo, nombre, es_semilla in CATEGORIAS_PRODUCTO:
            obj, created = CategoriaProducto.objects.get_or_create(
                codigo=codigo,
                defaults={"nombre": nombre, "es_semilla": es_semilla},
            )
            if created:
                self.stdout.write(f"  Categoría creada: {obj}")

    def _seed_cultivos(self, empresa_nombre):
        from agro.models import Empresa
        try:
            empresa = Empresa.objects.get(nombre=empresa_nombre)
        except Empresa.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Empresa '{empresa_nombre}' no encontrada."))
            return
        for nombre in CULTIVOS:
            obj, created = Cultivo.objects.get_or_create(nombre=nombre, defaults={"empresa": empresa})
            if created:
                self.stdout.write(f"  Cultivo creado: {obj}")

    def _seed_geografico(self):
        for pais_nombre, provincias in PAISES_PROVINCIAS_CIUDADES.items():
            pais, _ = Pais.objects.get_or_create(nombre=pais_nombre)
            for prov_nombre, ciudades in provincias.items():
                prov, _ = Provincia.objects.get_or_create(nombre=prov_nombre, defaults={"pais": pais})
                for ciudad_nombre in ciudades:
                    obj, created = Ciudad.objects.get_or_create(
                        nombre=ciudad_nombre, provincia=prov
                    )
                    if created:
                        self.stdout.write(f"  Ciudad creada: {obj}")
