"""
Carga stock inicial de insumos desde un CSV (separado por ';').

Por defecto solo muestra lo que haría; para grabar hay que pasar --confirmar.
Es seguro correrlo más de una vez: una entrada igual (producto, fecha, cantidad,
precio y depósito) que ya exista no se vuelve a crear.

Columnas del CSV:
    codigo_coop;producto;categoria;unidad;contenido_envase;envases;valor_total;fecha;nf;codigo_existente

- categoria:        código de CategoriaProducto (HER, INS, FUN, ...)
- unidad:           abreviatura de la unidad base (L, kg, ...)
- contenido_envase: litros/kg por envase
- valor_total:      valor del saldo de esa línea (no por envase)
- codigo_existente: código de un producto ya cargado; si está vacío se usa / crea COOP-<codigo_coop>

Uso:
    python manage.py importar_stock_inicial <archivo.csv> --empresa "Agroinnova"
    python manage.py importar_stock_inicial <archivo.csv> --empresa "Agroinnova" --confirmar
"""
import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from agro.models import Empresa, Unidad
from gestion_agro.models import CategoriaProducto, Deposito, MovimientoStock, Producto


class Command(BaseCommand):
    help = "Carga stock inicial de insumos desde un CSV. Sin --confirmar no graba nada."

    def add_arguments(self, parser):
        parser.add_argument("archivo")
        parser.add_argument("--empresa", required=True, help="Nombre o id de la empresa")
        parser.add_argument("--deposito", help="Nombre del depósito destino (default: depósito de insumos de la empresa)")
        parser.add_argument("--confirmar", action="store_true", help="Graba los cambios")

    def handle(self, *args, **opts):
        empresa = self._empresa(opts["empresa"])
        deposito = self._deposito(empresa, opts.get("deposito"))
        filas = self._leer(opts["archivo"])

        self.stdout.write(f"Empresa: {empresa.nombre} · Depósito: {deposito.nombre}")
        self.stdout.write("MODO PRUEBA: no se graba nada.\n" if not opts["confirmar"] else "GRABANDO.\n")

        with transaction.atomic():
            resumen = self._procesar(empresa, deposito, filas)
            if not opts["confirmar"]:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(
            f"Productos nuevos: {resumen['nuevos']} · Entradas nuevas: {resumen['entradas']} "
            f"· Ya existentes (se saltean): {resumen['repetidas']}"
        )
        self.stdout.write(f"Valor total cargado: R$ {resumen['valor']:,.2f}")
        if not opts["confirmar"]:
            self.stdout.write(self.style.WARNING("Nada fue grabado. Revise y vuelva a correr con --confirmar."))
        else:
            self.stdout.write(self.style.SUCCESS("Listo."))

    # ── auxiliares ──────────────────────────────────────────────────────────

    def _empresa(self, valor):
        qs = Empresa.objects.filter(id=valor) if str(valor).isdigit() else Empresa.objects.filter(nombre__iexact=valor)
        empresa = qs.first()
        if not empresa:
            raise CommandError(f"No existe la empresa '{valor}'.")
        return empresa

    def _deposito(self, empresa, nombre):
        if nombre:
            deposito = Deposito.objects.filter(empresa=empresa, nombre__iexact=nombre).first()
            if not deposito:
                raise CommandError(f"No existe el depósito '{nombre}' en {empresa.nombre}.")
            return deposito
        if not empresa.deposito_insumos_default:
            raise CommandError("La empresa no tiene depósito de insumos por defecto; indique --deposito.")
        return empresa.deposito_insumos_default

    def _unidad(self, abreviatura):
        # si hay varias con la misma abreviatura (ej. kg / Kgs) se usa la más usada por productos
        unidad = (
            Unidad.objects.filter(Q(abreviatura__iexact=abreviatura) | Q(nombre__iexact=abreviatura))
            .annotate(n=Count("productos_unidad_base"))
            .order_by("-n", "id")
            .first()
        )
        if not unidad:
            raise CommandError(f"No existe la unidad '{abreviatura}'.")
        return unidad

    def _leer(self, archivo):
        try:
            with open(archivo, encoding="utf-8") as f:
                filas = list(csv.DictReader(f, delimiter=";"))
        except FileNotFoundError:
            raise CommandError(f"No existe el archivo {archivo}.")
        for n, fila in enumerate(filas, start=2):
            try:
                fila["contenido_envase"] = Decimal(fila["contenido_envase"])
                fila["envases"] = Decimal(fila["envases"])
                fila["valor_total"] = Decimal(fila["valor_total"])
                fila["fecha"] = datetime.strptime(fila["fecha"], "%Y-%m-%d").date()
            except Exception as e:
                raise CommandError(f"Línea {n} del CSV inválida: {e}")
        return filas

    def _producto(self, empresa, fila, resumen):
        codigo = (fila.get("codigo_existente") or "").strip() or f"COOP-{fila['codigo_coop']}"
        producto = Producto.objects.filter(empresa=empresa, codigo=codigo).select_related("unidad_base").first()
        if producto:
            if producto.unidad_base_id != self._unidad(fila["unidad"]).id and \
                    producto.unidad_base.abreviatura.lower() not in (fila["unidad"].lower(), "kgs" if fila["unidad"].lower() == "kg" else ""):
                raise CommandError(
                    f"{producto.nombre} (código {codigo}) está en {producto.unidad_base} y el CSV en {fila['unidad']}. "
                    "Corrija el CSV o el producto antes de cargar."
                )
            return producto, "existente"

        categoria = CategoriaProducto.objects.filter(codigo=fila["categoria"]).first()
        if not categoria:
            raise CommandError(f"No existe la categoría '{fila['categoria']}' ({fila['producto']}).")
        producto = Producto.objects.create(
            empresa=empresa,
            codigo=codigo,
            nombre=fila["producto"],
            categoria=categoria,
            unidad_base=self._unidad(fila["unidad"]),
            maneja_stock=True,
            activo=True,
        )
        resumen["nuevos"] += 1
        return producto, "NUEVO"

    def _procesar(self, empresa, deposito, filas):
        resumen = {"nuevos": 0, "entradas": 0, "repetidas": 0, "valor": Decimal("0")}

        for fila in filas:
            producto, estado = self._producto(empresa, fila, resumen)
            unidad = producto.unidad_base
            cantidad = fila["envases"] * fila["contenido_envase"]
            precio = (fila["valor_total"] / cantidad).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            fecha = timezone.make_aware(datetime.combine(fila["fecha"], datetime.min.time()))

            stock_actual = sum(
                (m.cantidad if m.tipo == MovimientoStock.Tipo.ENTRADA else -m.cantidad)
                for m in MovimientoStock.objects.filter(producto=producto, um=unidad)
            )

            ya_existe = MovimientoStock.objects.filter(
                producto=producto, tipo=MovimientoStock.Tipo.ENTRADA, cantidad=cantidad,
                precio_unitario=precio, fecha=fecha, deposito_destino=deposito, factura_item__isnull=True,
            ).exists()

            linea = (
                f"[{estado:9}] {producto.nombre[:38]:38} NF {fila['nf']}  "
                f"{fila['envases']:>5} env = {cantidad:>8} {unidad.abreviatura:3}  "
                f"R$ {precio:>9.2f}/{unidad.abreviatura}  total R$ {fila['valor_total']:>10,.2f}  "
                f"(stock actual {stock_actual} {unidad.abreviatura})"
            )
            if ya_existe:
                resumen["repetidas"] += 1
                self.stdout.write(self.style.NOTICE("YA CARGADA  " + linea))
                continue

            MovimientoStock.objects.create(
                producto=producto,
                tipo=MovimientoStock.Tipo.ENTRADA,
                cantidad=cantidad,
                um=unidad,
                fecha=fecha,
                precio_unitario=precio,
                deposito_destino=deposito,
            )
            # precio de referencia (se usa si la empresa permite aplicar sin stock); no pisa uno ya cargado
            if not producto.precio:
                producto.precio = precio
                producto.save(update_fields=["precio"])
            elif estado == "existente" and abs(producto.precio - precio) > precio * Decimal("0.5"):
                self.stdout.write(self.style.WARNING(
                    f"    ⚠ {producto.nombre}: su precio cargado es {producto.precio} y en el extracto da {precio}/{unidad.abreviatura}. Revíselo."
                ))

            resumen["entradas"] += 1
            resumen["valor"] += fila["valor_total"]
            self.stdout.write("CARGA       " + linea)

        return resumen
