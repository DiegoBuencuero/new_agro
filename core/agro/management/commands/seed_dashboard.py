"""
Carga datos de demostración para visualizar el dashboard completo.
Idempotente: no duplica si se corre dos veces.

Uso:
    python manage.py seed_dashboard
    python manage.py seed_dashboard --reset   # borra los registros demo antes de recrear
"""
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

HOY = datetime.date.today()


def d(year, month, day):
    return datetime.date(year, month, day)


def mas(dias):
    return HOY + datetime.timedelta(days=dias)


def menos(dias):
    return HOY - datetime.timedelta(days=dias)


class Command(BaseCommand):
    help = "Carga datos demo para el dashboard"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Elimina los registros demo antes de recrear")

    def handle(self, *args, **options):
        from agro.models import Empresa
        from gestion_agro.models import (
            Campo, CicloAgricola, Cultivo, FaseAgricola,
            TipoActividad, ActividadProductiva,
            FacturaCompra, Proveedor, Cliente,
        )
        from administracion.models import (
            FacturaVenta, FacturaVentaItem, Pago, AplicacionPago,
            Recibo, AplicacionRecibo,
        )

        empresa = Empresa.objects.filter(nombre__icontains="agro").first() or Empresa.objects.first()
        if not empresa:
            self.stderr.write("No hay empresa en la DB. Creá una primero.")
            return

        self.stdout.write(f"Empresa: {empresa.nombre} (id={empresa.id})")

        if options["reset"]:
            self._reset(empresa)

        with transaction.atomic():
            self._seed_proveedores(empresa, Proveedor)
            self._seed_clientes(empresa, Cliente)
            self._seed_ciclos(empresa, Campo, CicloAgricola, Cultivo,
                              FaseAgricola, TipoActividad, ActividadProductiva)
            self._seed_facturas_compra(empresa, FacturaCompra, Proveedor,
                                       Pago, AplicacionPago)
            self._seed_facturas_venta(empresa, FacturaVenta, FacturaVentaItem,
                                      Cliente, Recibo, AplicacionRecibo)

        self.stdout.write(self.style.SUCCESS("✓ Datos demo cargados"))

    # ─────────────────────────────────────────────────────────
    def _reset(self, empresa):
        from gestion_agro.models import CicloAgricola, FacturaCompra
        from administracion.models import FacturaVenta, Pago, Recibo
        tag = "[DEMO]"
        Recibo.objects.filter(empresa=empresa,
                              referencia__startswith=tag).delete()
        Pago.objects.filter(empresa=empresa,
                            referencia__startswith=tag).delete()
        FacturaVenta.objects.filter(empresa=empresa,
                                    numero__startswith=tag).delete()
        FacturaCompra.objects.filter(empresa=empresa,
                                     numero__startswith=tag).delete()
        CicloAgricola.objects.filter(campo__empresa=empresa,
                                     nombre_lote__startswith=tag).delete()
        self.stdout.write("  Reset OK")

    # ─────────────────────────────────────────────────────────
    def _seed_proveedores(self, empresa, Proveedor):
        for razon, identificador in [
            ("Cooperativa Agrícola Sul Ltda", "04.111.222/0001-33"),
            ("Agroquímica Pampa S.A.",        "12.333.444/0001-55"),
            ("Sementes Rio Grande Ltda",       "08.555.666/0001-77"),
        ]:
            Proveedor.objects.get_or_create(
                empresa=empresa, identificador=identificador,
                defaults={"razon_social": razon},
            )
        self.stdout.write("  Proveedores OK")

    def _seed_clientes(self, empresa, Cliente):
        for razon, identificador in [
            ("Cerealista do Sul Ltda",      "11.222.333/0001-44"),
            ("Exportadora BMS S.A.",        "22.333.444/0001-66"),
            ("Armazém Geral Santa Rosa",    "33.444.555/0001-88"),
        ]:
            Cliente.objects.get_or_create(
                empresa=empresa, identificador=identificador,
                defaults={"razon_social": razon},
            )
        self.stdout.write("  Clientes OK")

    # ─────────────────────────────────────────────────────────
    def _seed_ciclos(self, empresa, Campo, CicloAgricola, Cultivo,
                     FaseAgricola, TipoActividad, ActividadProductiva):  # noqa: C901
        from gestion_agro.models import SubTipoActividad, Campana

        TAG = "[DEMO]"
        campana = Campana.objects.filter(empresa=empresa).first()
        if not campana:
            campana = Campana.objects.create(
                empresa=empresa, nombre="2024/2025",
                fecha_desde=d(2024, 7, 1), fecha_hasta=d(2025, 6, 30),
            )

        ibicui = Campo.objects.filter(empresa=empresa,
                                      nombre__icontains="ibicui").first()
        san_joan = Campo.objects.filter(empresa=empresa,
                                        nombre__icontains="san").first()
        soja  = Cultivo.objects.filter(nombre__iexact="soja").first()
        maiz  = Cultivo.objects.filter(nombre__icontains="maíz").first() or \
                Cultivo.objects.filter(nombre__icontains="maiz").first()
        trigo = Cultivo.objects.filter(nombre__iexact="trigo").first()

        tipo_siem  = TipoActividad.objects.filter(nombre__icontains="siem").first()
        tipo_aplic = TipoActividad.objects.filter(nombre__icontains="aplic").first()
        tipo_fert  = TipoActividad.objects.filter(nombre__icontains="ferti").first()
        tipo_mon   = TipoActividad.objects.filter(nombre__icontains="monit").first()

        nuevos = [
            # (campo, cultivo, ha, fecha_inicio, activa, lote_tag)
            (ibicui,   soja,  250, menos(210), True,  TAG+"IBICUI-SOJA"),
            (ibicui,   maiz,  180, menos(155), True,  TAG+"IBICUI-MAIZ"),
            (san_joan, maiz,  120, menos(130), True,  TAG+"SANJOAN-MAIZ"),
            (san_joan, trigo,  90, menos(280), False, TAG+"SANJOAN-TRIGO"),
        ]

        for campo, cultivo, ha, fecha_ini, activa, lote_tag in nuevos:
            if not campo or not cultivo:
                continue
            ciclo, created = CicloAgricola.objects.get_or_create(
                campo=campo,
                cultivo=cultivo,
                nombre_lote=lote_tag,
                defaults={
                    "campana":       campana,
                    "activa":        activa,
                    "superficie_ha": Decimal(str(ha)),
                    "fecha_inicio":  fecha_ini,
                    "fecha_fin":     None if activa else menos(30),
                },
            )
            if not created:
                continue

            # Fase principal
            fase, _ = FaseAgricola.objects.get_or_create(
                ciclo=ciclo, tipo="PRI",
                defaults={
                    "fecha_inicio": fecha_ini,
                    "fecha_fin":    None if activa else menos(30),
                    "estado":       "abierto" if activa else "cerrado",
                },
            )

            # Actividades distribuidas desde el inicio
            if activa and tipo_siem:
                offset = 0
                for tipo_act, delta in [
                    (tipo_siem,  0),
                    (tipo_aplic, 30),
                    (tipo_fert,  55),
                    (tipo_aplic, 80),
                    (tipo_mon,   110),
                    (tipo_fert,  140),
                    (tipo_mon,   170),
                ]:
                    if not tipo_act:
                        continue
                    act_fecha = fecha_ini + datetime.timedelta(days=delta)
                    if act_fecha > HOY:
                        break
                    total_val = Decimal("1200") + Decimal(str(delta * 10))
                    ActividadProductiva.objects.get_or_create(
                        fase=fase,
                        tipo=tipo_act,
                        fecha=act_fecha,
                        defaults={
                            "total": total_val,
                            "total_mo": total_val * Decimal("0.3"),
                            "total_maq": total_val * Decimal("0.7"),
                        },
                    )

        self.stdout.write("  Ciclos y actividades OK")

    # ─────────────────────────────────────────────────────────
    def _seed_facturas_compra(self, empresa, FacturaCompra, Proveedor,
                              Pago, AplicacionPago):
        TAG = "[DEMO]"

        provs = list(Proveedor.objects.filter(empresa=empresa))
        if not provs:
            return
        p0, p1, p2 = provs[0], provs[min(1, len(provs)-1)], provs[min(2, len(provs)-1)]

        # (numero_tag, proveedor, total, fecha, fecha_vto, pago_parcial)
        facturas = [
            # Históricas (calendrio) — meses anteriores
            (TAG+"FC-001", p1, Decimal("85000"),  menos(300), None,           Decimal("85000")),
            (TAG+"FC-002", p2, Decimal("125000"), menos(270), None,           Decimal("62500")),
            (TAG+"FC-003", p0, Decimal("95000"),  menos(240), None,           Decimal("95000")),
            (TAG+"FC-004", p1, Decimal("180000"), menos(210), None,           Decimal("90000")),
            (TAG+"FC-005", p2, Decimal("45000"),  menos(180), None,           Decimal("45000")),
            (TAG+"FC-006", p0, Decimal("210000"), menos(150), None,           Decimal("105000")),
            (TAG+"FC-007", p1, Decimal("75000"),  menos(120), None,           Decimal("37500")),
            (TAG+"FC-008", p2, Decimal("160000"), menos(90),  None,           Decimal("80000")),
            # Pendientes (sin fecha_vto o con vto futura)
            (TAG+"FC-009", p0, Decimal("140000"), menos(60),  mas(25),        Decimal("20000")),
            (TAG+"FC-010", p1, Decimal("58000"),  menos(45),  mas(18),        Decimal("0")),
            (TAG+"FC-011", p2, Decimal("32000"),  menos(30),  mas(35),        Decimal("0")),
            (TAG+"FC-012", p0, Decimal("92000"),  menos(20),  mas(8),         Decimal("0")),
            (TAG+"FC-013", p1, Decimal("25000"),  menos(15),  mas(5),         Decimal("0")),
            (TAG+"FC-014", p2, Decimal("18000"),  menos(10),  mas(3),         Decimal("0")),
        ]

        for numero, prov, total, fecha, fecha_vto, pagado in facturas:
            fc, created = FacturaCompra.objects.get_or_create(
                empresa=empresa, numero=numero,
                defaults={
                    "proveedor":          prov,
                    "total":              total,
                    "fecha":              fecha,
                    "fecha_vencimiento":  fecha_vto,
                },
            )
            if not created or pagado == 0:
                continue
            pago = Pago.objects.create(
                empresa=empresa,
                proveedor=prov,
                fecha=fecha + datetime.timedelta(days=5),
                medio_pago="TRF",
                referencia=TAG + "auto",
            )
            AplicacionPago.objects.create(
                pago=pago,
                factura=fc,
                monto_aplicado=pagado,
            )

        self.stdout.write("  Facturas compra OK")

    # ─────────────────────────────────────────────────────────
    def _seed_facturas_venta(self, empresa, FacturaVenta, FacturaVentaItem,
                             Cliente, Recibo, AplicacionRecibo):
        from gestion_agro.models import Producto
        TAG = "[DEMO]"

        clientes = list(Cliente.objects.filter(empresa=empresa))
        if not clientes:
            return
        c0, c1, c2 = clientes[0], clientes[min(1,len(clientes)-1)], clientes[min(2,len(clientes)-1)]

        soja_prod  = Producto.objects.filter(empresa=empresa, nombre__icontains="soja", producto_final=True).first()
        maiz_prod  = Producto.objects.filter(empresa=empresa, nombre__icontains="maíz", producto_final=True).first() or \
                     Producto.objects.filter(empresa=empresa, nombre__icontains="maiz", producto_final=True).first()
        trigo_prod = Producto.objects.filter(empresa=empresa, nombre__icontains="trigo", producto_final=True).first()

        # (numero_tag, cliente, producto, cant_sc, precio_sc, fecha, fecha_vto, cobrado)
        ventas = [
            # Históricas
            (TAG+"FV-001", c0, soja_prod,  3000, Decimal("123"), menos(250), None,       Decimal("369000")),
            (TAG+"FV-002", c1, maiz_prod,  1800, Decimal("52"),  menos(220), None,       Decimal("93600")),
            (TAG+"FV-003", c0, soja_prod,  4500, Decimal("126"), menos(180), None,       Decimal("283500")),
            (TAG+"FV-004", c2, trigo_prod,  900, Decimal("70"),  menos(150), None,       Decimal("63000")),
            (TAG+"FV-005", c1, soja_prod,  2200, Decimal("127"), menos(120), None,       Decimal("139700")),
            (TAG+"FV-006", c0, maiz_prod,  2500, Decimal("53"),  menos(90),  None,       Decimal("66250")),
            (TAG+"FV-007", c2, soja_prod,  3800, Decimal("129"), menos(60),  None,       Decimal("245100")),
            # Pendientes de cobro
            (TAG+"FV-008", c0, soja_prod,  5200, Decimal("131"), menos(35),  mas(20),    Decimal("270400")),
            (TAG+"FV-009", c1, maiz_prod,  1500, Decimal("54"),  menos(25),  mas(15),    Decimal("0")),
            (TAG+"FV-010", c2, soja_prod,  2800, Decimal("131"), menos(15),  mas(10),    Decimal("0")),
            (TAG+"FV-011", c0, trigo_prod,  600, Decimal("71"),  menos(10),  mas(6),     Decimal("0")),
            (TAG+"FV-012", c1, soja_prod,  1200, Decimal("132"), menos(5),   mas(3),     Decimal("0")),
        ]

        for numero, cliente, prod, cant, precio, fecha, fecha_vto, cobrado in ventas:
            if not prod:
                continue
            fv, created = FacturaVenta.objects.get_or_create(
                empresa=empresa, numero=numero,
                defaults={
                    "cliente":           cliente,
                    "fecha":             fecha,
                    "fecha_vencimiento": fecha_vto,
                },
            )
            if not created:
                continue
            FacturaVentaItem.objects.create(
                factura=fv,
                producto=prod,
                cantidad=Decimal(str(cant)),
                precio_unitario=precio,
            )
            if cobrado and cobrado > 0:
                recibo = Recibo.objects.create(
                    empresa=empresa,
                    cliente=cliente,
                    fecha=fecha + datetime.timedelta(days=7),
                    medio_cobro="TRF",
                    referencia=TAG + "auto",
                )
                AplicacionRecibo.objects.create(
                    recibo=recibo,
                    factura=fv,
                    monto_aplicado=cobrado,
                )

        self.stdout.write("  Facturas venta OK")
