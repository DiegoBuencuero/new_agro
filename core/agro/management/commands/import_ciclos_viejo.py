"""
Limpia los datos operativos de new_agro e importa los ciclos
reales de la campaña 2025/2026 del sistema viejo.

Uso:
    python manage.py import_ciclos_viejo           # dry-run (solo muestra lo que haría)
    python manage.py import_ciclos_viejo --confirm  # ejecuta el proceso completo
"""
import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

# ─── Datos del sistema viejo ──────────────────────────────────────────────────

CAMPO_MAP = {
    1: "Ibicui",     # → busca IBICUI en new_agro
    2: "São João",   # → busca San Joan en new_agro
    3: "Unbu",       # → no existe, se crea
}

# Clave de búsqueda para icontains (evita problemas con acentos/transliteraciones)
CAMPO_SEARCH = {
    1: "ibicu",
    2: "san",     # "San Joan" contiene "san"
    3: "Unbu",
}

CULTIVO_MAP = {
    1: "Trigo",
    2: "Soja",
    3: "Maíz",
    4: "Feijão",     # no existe, se crea
}

CICLOS = [
    {"old_id": 18, "campo_old": 1, "lote": "Lote-1", "cultivo_old": 1,
     "ha": 125, "inicio": "2025-03-01", "fin": "2026-02-03", "activa": False},
    {"old_id": 19, "campo_old": 2, "lote": "Lote-1", "cultivo_old": 2,
     "ha": 182, "inicio": "2025-10-01", "fin": "2026-04-08", "activa": False},
    {"old_id": 20, "campo_old": 3, "lote": "Lote-1", "cultivo_old": 4,
     "ha": 40,  "inicio": "2025-12-19", "fin": None,        "activa": True},
    {"old_id": 21, "campo_old": 1, "lote": "Lote-2", "cultivo_old": 2,
     "ha": 125, "inicio": "2025-11-28", "fin": None,        "activa": True},
]

# Una fase por ciclo (tipo PRI = cultivo principal)
FASES = {
    18: {"inicio": "2025-03-01", "fin": "2026-02-03", "estado": "cerrado"},
    19: {"inicio": "2025-10-15", "fin": "2026-04-08", "estado": "cerrado"},
    20: {"inicio": "2025-12-19", "fin": None,         "estado": "abierto"},
    21: {"inicio": "2025-11-28", "fin": None,         "estado": "abierto"},
}

TIPO_ACT_MAP = {
    "siembra":       "Siembra",
    "aplicacion":    "Aplicación",
    "fertilizacion": "Fertilización",
    "cosecha":       "Cosecha",
    "monitoreo":     "Monitoreo",
}

# Costos de insumos pre-sumados por actividad (old_act_id → total R$)
INSUMO_COSTS = {
    68:  Decimal("15625.00"),
    69:  Decimal("3589.69"),
    74:  Decimal("79500.00"),
    76:  Decimal("67500.00") + Decimal("146125.00"),
    77:  Decimal("22031.25") + Decimal("5000.00") + Decimal("1875.00"),
    78:  Decimal("2000.00")  + Decimal("625.00"),
    82:  Decimal("7500.00")  + Decimal("5000.00") + Decimal("625.00") + Decimal("625.00"),
    83:  Decimal("0"),
    84:  Decimal("94875.00") + Decimal("156625.00"),
    85:  Decimal("5568.75"),
    87:  Decimal("7425.00"),
    88:  Decimal("5568.75")  + Decimal("13875.00") + Decimal("3125.00") + Decimal("1437.50"),
    91:  Decimal("8108.10")  + Decimal("8699.60")  + Decimal("1088.36") + Decimal("531.81"),
    92:  Decimal("2702.70"),
    94:  Decimal("136045.00") + Decimal("194521.60"),
    97:  Decimal("8108.10")  + Decimal("2730.00")  + Decimal("5460.00") + Decimal("13650.00") + Decimal("531.81"),
    100: Decimal("8108.10")  + Decimal("9100.00")  + Decimal("6370.00") + Decimal("2184.00")  + Decimal("531.81"),
    101: Decimal("2376.00")  + Decimal("440.00")   + Decimal("5828.57") + Decimal("233.76"),
    103: Decimal("53120.00") + Decimal("60120.00"),
    105: Decimal("800.00")   + Decimal("350.00")   + Decimal("2400.00") + Decimal("600.00")   + Decimal("116.88"),
    106: Decimal("19080.00"),
    107: Decimal("440.00")   + Decimal("3000.00")  + Decimal("933.82")  + Decimal("256.00")   + Decimal("600.00"),
    108: Decimal("4900.00"),
    111: Decimal("0"),
}

# Actividades: (old_fase_id, old_act_id, fecha, tipo)
ACTIVIDADES = [
    # Ciclo 18 - Ibicui Trigo (fases 25 y 26 → fusionadas en una)
    (18, 68,  "2025-03-25", "siembra"),
    (18, 69,  "2025-05-27", "aplicacion"),
    (18, 76,  "2025-07-05", "siembra"),
    (18, 77,  "2025-08-11", "aplicacion"),
    (18, 78,  "2025-08-14", "aplicacion"),
    (18, 74,  "2025-08-22", "fertilizacion"),
    (18, 82,  "2025-11-05", "aplicacion"),
    (18, 83,  "2025-11-28", "cosecha"),
    # Ciclo 19 - São João Soja (fase 30)
    (19, 91,  "2025-10-15", "aplicacion"),
    (19, 92,  "2025-10-22", "aplicacion"),
    (19, 94,  "2025-11-05", "siembra"),
    (19, 97,  "2025-12-10", "aplicacion"),
    (19, 100, "2026-01-07", "aplicacion"),
    (19, 108, "2026-04-08", "aplicacion"),
    (19, 111, "2026-04-08", "cosecha"),
    # Ciclo 20 - Unbu Feijão (fase 31)
    (20, 101, "2025-12-19", "aplicacion"),
    (20, 103, "2025-12-20", "siembra"),
    (20, 105, "2026-01-14", "aplicacion"),
    (20, 106, "2026-01-16", "fertilizacion"),
    (20, 107, "2026-02-01", "aplicacion"),
    # Ciclo 21 - Ibicui Soja (fase 27)
    (21, 84,  "2025-11-28", "siembra"),
    (21, 85,  "2025-11-29", "aplicacion"),
    (21, 87,  "2025-12-25", "aplicacion"),
    (21, 88,  "2026-01-19", "aplicacion"),
]


class Command(BaseCommand):
    help = "Limpia datos operativos e importa ciclos del sistema viejo"

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true",
                            help="Ejecuta la limpieza e importación (sin esto solo muestra el plan)")

    def handle(self, *args, **options):
        confirmar = options["confirm"]

        if not confirmar:
            self._mostrar_plan()
            self.stdout.write("\n" + self.style.WARNING(
                "Revisá el plan y corré con --confirm para ejecutar."
            ))
            return

        with transaction.atomic():
            self._limpiar()
            self._importar()

        self.stdout.write(self.style.SUCCESS("\n✓ Importación completada"))

    # ─── Plan (dry-run) ───────────────────────────────────────────────────────
    def _mostrar_plan(self):
        self.stdout.write("\n── PLAN ─────────────────────────────────────────")
        self.stdout.write("LIMPIAR:")
        self.stdout.write("  • CicloAgricola + FaseAgricola + ActividadProductiva")
        self.stdout.write("  • FacturaCompra + AplicacionPago + Pago")
        self.stdout.write("  • FacturaVenta + AplicacionRecibo + Recibo")
        self.stdout.write("  • MovimientoStock")
        self.stdout.write("\nIMPORTAR:")
        for c in CICLOS:
            campo  = CAMPO_MAP[c["campo_old"]]
            cultiv = CULTIVO_MAP[c["cultivo_old"]]
            estado = "ACTIVO" if c["activa"] else "CERRADO"
            acts   = [a for a in ACTIVIDADES if a[0] == c["old_id"]]
            self.stdout.write(
                f"  • {campo} — {cultiv} {c['ha']}ha [{estado}]"
                f"  {len(acts)} actividades"
            )
        self.stdout.write("")

    # ─── Limpieza ─────────────────────────────────────────────────────────────
    def _limpiar(self):
        from gestion_agro.models import CicloAgricola, FacturaCompra, MovimientoStock
        from administracion.models import FacturaVenta, Pago, Recibo

        empresa = self._empresa()

        # Cascada automática desde CicloAgricola → FaseAgricola → Actividades
        n = CicloAgricola.objects.filter(campo__empresa=empresa).delete()
        self.stdout.write(f"  Ciclos eliminados: {n}")

        FacturaCompra.objects.filter(empresa=empresa).delete()
        FacturaVenta.objects.filter(empresa=empresa).delete()
        Pago.objects.filter(empresa=empresa).delete()
        Recibo.objects.filter(empresa=empresa).delete()
        MovimientoStock.objects.filter(
            producto__empresa=empresa
        ).delete()

        self.stdout.write("  Limpieza OK")

    # ─── Importación ──────────────────────────────────────────────────────────
    def _importar(self):
        from gestion_agro.models import (
            Campo, Cultivo, Campana, CicloAgricola,
            FaseAgricola, TipoActividad, ActividadProductiva,
            Producto, CategoriaProducto,
        )
        from agro.models import Unidad

        empresa = self._empresa()

        # 1. Resolución de campos
        ciudad_default = Campo.objects.filter(empresa=empresa).values_list("ciudad_id", flat=True).first()

        campo_new = {}
        for old_id, nombre in CAMPO_MAP.items():
            search = CAMPO_SEARCH.get(old_id, nombre[:5])
            campo = Campo.objects.filter(empresa=empresa, nombre__icontains=search).first()
            if not campo:
                campo = Campo.objects.create(
                    empresa=empresa, nombre=nombre,
                    superficie_ha=Decimal("50"),
                    ciudad_id=ciudad_default,
                )
                self.stdout.write(f"  Campo creado: {nombre}")
            campo_new[old_id] = campo

        # 2. Resolución de cultivos (con producto_default obligatorio)
        cultivo_new = {}
        for old_id, nombre in CULTIVO_MAP.items():
            cultivo = Cultivo.objects.filter(empresa=empresa, nombre__iexact=nombre).first()
            if not cultivo:
                cultivo = Cultivo.objects.create(empresa=empresa, nombre=nombre)
                self.stdout.write(f"  Cultivo creado: {nombre}")
            # Asegurar que tiene producto_default (requerido por CicloAgricola.clean)
            if not cultivo.producto_default:
                cat_final = CategoriaProducto.objects.filter(nombre__icontains="final").first()
                unidad_kg = Unidad.objects.filter(nombre__icontains="kilo").first()
                prod, _ = Producto.objects.get_or_create(
                    empresa=empresa,
                    nombre=f"{nombre} grano",
                    defaults={
                        "codigo":        nombre.lower()[:20],
                        "categoria":     cat_final,
                        "unidad_base":   unidad_kg,
                        "precio":        Decimal("0"),
                        "maneja_stock":  False,
                        "producto_final": True,
                        "activo":        True,
                    },
                )
                cultivo.producto_default = prod
                cultivo.save()
                self.stdout.write(f"  Producto default creado: {prod.nombre}")
            cultivo_new[old_id] = cultivo

        # 3. Campaña
        campana, _ = Campana.objects.get_or_create(
            empresa=empresa, nombre="2025/2026",
            defaults={
                "fecha_desde": datetime.date(2025, 3, 1),
                "fecha_hasta": datetime.date(2026, 4, 30),
                "activa": False,
            }
        )

        # 4. TipoActividad map
        tipo_map = {}
        for old_tipo, new_nombre in TIPO_ACT_MAP.items():
            ta = TipoActividad.objects.filter(nombre__icontains=new_nombre[:5]).first()
            if ta:
                tipo_map[old_tipo] = ta

        # 5. Ciclos → Fases → Actividades
        for c in CICLOS:
            ciclo = CicloAgricola.objects.create(
                campo=campo_new[c["campo_old"]],
                campana=campana,
                cultivo=cultivo_new[c["cultivo_old"]],
                nombre_lote=c["lote"],
                superficie_ha=Decimal(str(c["ha"])),
                fecha_inicio=datetime.date.fromisoformat(c["inicio"]),
                fecha_fin=datetime.date.fromisoformat(c["fin"]) if c["fin"] else None,
                activa=c["activa"],
            )
            self.stdout.write(
                f"  Ciclo: {ciclo.campo.nombre} — {ciclo.cultivo.nombre} "
                f"{'(activo)' if ciclo.activa else '(cerrado)'}"
            )

            f = FASES[c["old_id"]]
            fase = FaseAgricola.objects.create(
                ciclo=ciclo,
                tipo="PRI",
                fecha_inicio=datetime.date.fromisoformat(f["inicio"]),
                fecha_fin=datetime.date.fromisoformat(f["fin"]) if f["fin"] else None,
                estado=f["estado"],
            )

            acts = [a for a in ACTIVIDADES if a[0] == c["old_id"]]
            for _, old_act_id, fecha_str, tipo_str in acts:
                ta = tipo_map.get(tipo_str)
                if not ta:
                    continue
                costo = INSUMO_COSTS.get(old_act_id, Decimal("0"))
                ActividadProductiva.objects.create(
                    fase=fase,
                    tipo=ta,
                    fecha=datetime.date.fromisoformat(fecha_str),
                    total=costo,
                    total_mo=Decimal("0"),
                    total_maq=costo,
                )

            self.stdout.write(f"    → {len(acts)} actividades")

    # ─── Helpers ──────────────────────────────────────────────────────────────
    def _empresa(self):
        from agro.models import Empresa
        return Empresa.objects.filter(nombre__icontains="agro").first() or Empresa.objects.first()
