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

--reemplazar-stock borra antes TODOS los movimientos de stock de los insumos de la
empresa (todo producto que no sea producto final / cosecha), así el stock queda
exactamente igual al CSV. Los productos no se borran; el stock de cosecha no se toca.

Uso:
    python manage.py importar_stock_inicial <archivo.csv> --empresa "Agroinnova"
    python manage.py importar_stock_inicial <archivo.csv> --empresa "Agroinnova" --confirmar
    python manage.py importar_stock_inicial <archivo.csv> --empresa "Agroinnova" --reemplazar-stock --confirmar
"""
import csv
import re
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
        parser.add_argument("--reemplazar-stock", action="store_true",
                            help="Borra antes todo el stock de insumos de la empresa (no toca la cosecha)")

    def handle(self, *args, **opts):
        empresa = self._empresa(opts["empresa"])
        deposito = self._deposito(empresa, opts.get("deposito"))
        filas = self._leer(opts["archivo"])

        self.stdout.write(f"Empresa: {empresa.nombre} · Depósito destino: {deposito.nombre}")
        otros = ", ".join(Deposito.objects.filter(empresa=empresa).exclude(id=deposito.id).values_list("nombre", flat=True))
        if otros:
            self.stdout.write(f"  (otros depósitos: {otros} — se elige con --deposito \"<nombre>\")")
        self.stdout.write("MODO PRUEBA: no se graba nada.\n" if not opts["confirmar"] else "GRABANDO.\n")

        # se valida todo el CSV antes de borrar o grabar nada
        for fila in filas:
            fila["_categoria"] = self._categoria(fila)
            fila["_unidad"] = self._unidad(fila["unidad"])

        with transaction.atomic():
            if opts["reemplazar_stock"]:
                self._borrar_stock_insumos(empresa)
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

    def _borrar_stock_insumos(self, empresa):
        movimientos = MovimientoStock.objects.filter(producto__empresa=empresa, producto__producto_final=False)
        self.stdout.write(self.style.WARNING("SE BORRA el stock actual de insumos:"))
        saldos = {}
        for m in movimientos.select_related("producto", "um"):
            clave = (m.producto.nombre, m.um.abreviatura if m.um else "")
            saldos[clave] = saldos.get(clave, Decimal("0")) + (m.cantidad if m.tipo == MovimientoStock.Tipo.ENTRADA else -m.cantidad)
        for (nombre, um), saldo in sorted(saldos.items()):
            self.stdout.write(f"    {nombre[:45]:45} saldo {saldo:>12} {um}")
        total = movimientos.count()
        movimientos.delete()
        self.stdout.write(self.style.WARNING(f"    {total} movimientos borrados · el stock de cosecha no se toca\n"))

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

    CATEGORIA_NOMBRES = {
        "HER": ["herbicida"],
        "INS": ["insecticida", "inseticida"],
        "FUN": ["fungicida"],
        "FER": ["fertilizante"],
        "SEM": ["semilla", "semente"],
    }

    def _categoria(self, fila):
        codigo = fila["categoria"].strip()
        categoria = CategoriaProducto.objects.filter(codigo__iexact=codigo).first()
        if categoria:
            return categoria
        for nombre in self.CATEGORIA_NOMBRES.get(codigo.upper(), []):
            categoria = (
                CategoriaProducto.objects.filter(nombre__iexact=nombre).first()
                or CategoriaProducto.objects.filter(nombre__istartswith=nombre[:6]).first()
            )
            if categoria:
                return categoria
        disponibles = ", ".join(f"{c.codigo}={c.nombre}" for c in CategoriaProducto.objects.all())
        raise CommandError(
            f"No existe la categoría '{codigo}' ({fila['producto']}). Categorías en esta base: {disponibles}"
        )

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

    @staticmethod
    def _codigo_automatico(nombre):
        # mismo criterio que usa el sistema al crear productos desde facturas
        return re.sub(r"[^A-Z0-9]", "", nombre.upper())[:20]

    def _buscar_existente(self, empresa, fila):
        insumos = Producto.objects.filter(empresa=empresa, producto_final=False).select_related("unidad_base")
        codigos = [
            (fila.get("codigo_existente") or "").strip(),
            f"COOP-{fila['codigo_coop']}",
            self._codigo_automatico(fila["producto"]),
        ]
        for codigo in filter(None, codigos):
            producto = insumos.filter(codigo=codigo).first()
            if producto:
                return producto
        return (
            insumos.filter(nombre__iexact=fila["producto"]).first()
            or insumos.filter(nombre__istartswith=fila["producto"]).first()
        )

    def _producto(self, empresa, fila, resumen):
        producto = self._buscar_existente(empresa, fila)
        if producto:
            if producto.unidad_base_id != fila["_unidad"].id and \
                    producto.unidad_base.abreviatura.lower() not in (fila["unidad"].lower(), "kgs" if fila["unidad"].lower() == "kg" else ""):
                raise CommandError(
                    f"{producto.nombre} (código {producto.codigo}) está en {producto.unidad_base} y el CSV en {fila['unidad']}. "
                    "Corrija el CSV o el producto antes de cargar."
                )
            return producto, "existente"

        producto = Producto.objects.create(
            empresa=empresa,
            codigo=f"COOP-{fila['codigo_coop']}",
            nombre=fila["producto"],
            categoria=fila["_categoria"],
            unidad_base=fila["_unidad"],
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
