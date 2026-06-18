from django.core.management.base import BaseCommand
from gestion_agro.models import (
    TipoActividad, SubTipoActividad,
    CategoriaProducto, TipoActividadCategoriaProducto,
)

# (nombre_tipo_icontains, subtipo_codigo_o_None, [codigos_categoria])
REGLAS = [
    # Plantio + Adubação → semillas Y fertilizantes
    ("Plantio",       None,  ["SEMILLA", "FERTILIZANTE"]),

    # Adubação cobertura → solo fertilizantes
    ("Adubação cob",  None,  ["FERTILIZANTE"]),

    # Aplicação → agroquímicos + adjuvantes (por subtipo y fallback general)
    ("Aplicação",     None,  ["AGROQUIMICO", "ADJUVANTE"]),
    ("Aplicação",     "DES", ["AGROQUIMICO", "ADJUVANTE"]),
    ("Aplicação",     "HER", ["AGROQUIMICO", "ADJUVANTE"]),
    ("Aplicação",     "INS", ["AGROQUIMICO", "ADJUVANTE"]),
    ("Aplicação",     "FUN", ["AGROQUIMICO", "ADJUVANTE"]),
    ("Aplicação",     "HIN", ["AGROQUIMICO", "ADJUVANTE"]),
    ("Aplicação",     "IFU", ["AGROQUIMICO", "ADJUVANTE"]),
    ("Aplicação",     "MIS", ["AGROQUIMICO", "ADJUVANTE"]),
    ("Aplicação",     "FOL", ["FERTILIZANTE", "ADJUVANTE"]),

    # Tratamento sementes → agroquímicos (fungicidas/inseticidas de semilla)
    ("Tratamento",    None,  ["AGROQUIMICO"]),

    # Outros → insumos generales
    ("Outros",        None,  ["INSUMO"]),
]


class Command(BaseCommand):
    help = "Configura las categorías de producto permitidas por tipo de actividad"

    def handle(self, *args, **options):
        self.stdout.write("\n=== Tipos de actividad ===")
        tipos = {t.nombre: t for t in TipoActividad.objects.all()}
        for nombre, t in tipos.items():
            self.stdout.write(f"  [{t.id}] '{nombre}' (tipo={t.tipo})")

        self.stdout.write("\n=== Categorías ===")
        cats = {c.codigo: c for c in CategoriaProducto.objects.all()}
        for codigo, cat in cats.items():
            self.stdout.write(f"  '{codigo}' → {cat.nombre}")

        self.stdout.write("\n=== Aplicando reglas ===")
        created_total = 0

        for tipo_contains, subtipo_codigo, cat_codigos in REGLAS:
            tipo = next(
                (t for nombre, t in tipos.items()
                 if tipo_contains.lower() in nombre.lower()),
                None
            )
            if not tipo:
                self.stdout.write(f"  SKIP tipo: nada coincide con '{tipo_contains}'")
                continue

            subtipo = None
            if subtipo_codigo:
                subtipo = SubTipoActividad.objects.filter(
                    tipo_actividad=tipo, codigo=subtipo_codigo
                ).first()
                if not subtipo:
                    self.stdout.write(
                        f"  SKIP subtipo '{subtipo_codigo}' no encontrado en '{tipo.nombre}'"
                    )
                    continue

            for cat_codigo in cat_codigos:
                cat = cats.get(cat_codigo)
                if not cat:
                    self.stdout.write(f"  SKIP cat '{cat_codigo}' no existe en DB")
                    continue

                obj, created = TipoActividadCategoriaProducto.objects.get_or_create(
                    tipo_actividad=tipo,
                    subtipo_actividad=subtipo,
                    categoria_producto=cat,
                    defaults={"activo": True},
                )
                if not obj.activo:
                    obj.activo = True
                    obj.save()

                label = f"'{tipo.nombre}' / {subtipo_codigo or '-'} → {cat_codigo}"
                self.stdout.write(
                    self.style.SUCCESS(f"  {'CREADO' if created else 'YA OK '}: {label}")
                )
                if created:
                    created_total += 1

        self.stdout.write(f"\n=== Listo. {created_total} relaciones nuevas ===\n")
