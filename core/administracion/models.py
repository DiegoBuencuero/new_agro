from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from gestion_agro.models import FacturaCompra, Proveedor, Cliente
from agro.models import Empresa
from gestion_agro.models import Producto


class Pago(models.Model):
    MEDIO_PAGO = [
        ("TRF", _("Transferencia")),
        ("CHQ", _("Cheque")),
        ("EFE", _("Efectivo")),
        ("DEB", _("Débito automático")),
    ]

    empresa       = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    proveedor     = models.ForeignKey(Proveedor, on_delete=models.CASCADE, verbose_name=_("Proveedor"))
    numero        = models.PositiveIntegerField(default=0, verbose_name=_("N° orden"))
    fecha         = models.DateField(verbose_name=_("Fecha"))
    medio_pago    = models.CharField(max_length=3, choices=MEDIO_PAGO, default="TRF", verbose_name=_("Medio de pago"))
    referencia    = models.CharField(max_length=100, blank=True, default="", verbose_name=_("Referencia"))
    observaciones = models.TextField(blank=True, null=True, verbose_name=_("Observaciones"))
    creado        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Pago")
        verbose_name_plural = _("Pagos")
        ordering = ["-fecha", "-numero"]

    def __str__(self):
        return f"OP-{self.numero:05d} – {self.proveedor} – ${self.monto_total}"

    @property
    def monto_total(self):
        return self.aplicaciones.aggregate(total=Sum("monto_aplicado"))["total"] or 0


class AplicacionPago(models.Model):
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name="aplicaciones", verbose_name=_("Pago"))
    factura = models.ForeignKey(FacturaCompra, on_delete=models.CASCADE, related_name="aplicaciones", verbose_name=_("Factura"))
    monto_aplicado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Monto aplicado"))

    class Meta:
        verbose_name = _("Aplicación de pago")
        verbose_name_plural = _("Aplicaciones de pago")

    def __str__(self):
        return f"${self.monto_aplicado} → {self.factura}"


class FacturaVenta(models.Model): #VER TEMA IMPUESTO
    empresa  = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    cliente  = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name=_("Cliente"))
    numero   = models.CharField(max_length=20, verbose_name=_("NF-e número"))
    fecha             = models.DateField(verbose_name=_("Fecha"))
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name=_("Fecha vencimiento"))
    archivo_pdf       = models.FileField(upload_to="facturas_venta/", blank=True, null=True, verbose_name=_("PDF"))
    creada            = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Usuario que creó"))

    class Meta:
        verbose_name = _("Factura de venta")
        verbose_name_plural = _("Facturas de venta")

        ordering = ["-fecha"]


class FacturaVentaItem(models.Model):
    DESTINO_CHOICES = [("M", "Semilla (Multiplicación)"), ("C", "Consumo")]

    factura         = models.ForeignKey(FacturaVenta, related_name="items", on_delete=models.CASCADE)
    producto        = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad        = models.DecimalField(max_digits=12, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    deposito_origen = models.ForeignKey(
        "gestion_agro.Deposito", on_delete=models.PROTECT,
        null=True, blank=True, verbose_name=_("Depósito origen"),
    )
    destino = models.CharField(
        max_length=1, choices=DESTINO_CHOICES,
        null=True, blank=True, verbose_name=_("Destino"),
    )
    um = models.ForeignKey(
        "agro.Unidad", on_delete=models.PROTECT,
        null=True, blank=True, verbose_name=_("Unidad de medida"),
    )

    class Meta:
        verbose_name = _("Ítem de factura de venta")
        verbose_name_plural = _("Ítems de factura de venta")

    def __str__(self):
        return f"{self.producto} — {self.cantidad}"


class Recibo(models.Model):
    MEDIO_COBRO = [
        ("TRF", _("Transferencia")),
        ("CHQ", _("Cheque")),
        ("EFE", _("Efectivo")),
        ("DEB", _("Débito automático")),
    ]

    empresa       = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    cliente       = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name=_("Cliente"))
    numero        = models.PositiveIntegerField(default=0, verbose_name=_("N° recibo"))
    fecha         = models.DateField(default=__import__('datetime').date.today, verbose_name=_("Fecha"))
    medio_cobro   = models.CharField(max_length=3, choices=MEDIO_COBRO, default="TRF", verbose_name=_("Medio de cobro"))
    referencia    = models.CharField(max_length=100, blank=True, default="", verbose_name=_("Referencia"))
    observaciones = models.TextField(blank=True, null=True, verbose_name=_("Observaciones"))
    creado        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Recibo")
        verbose_name_plural = _("Recibos")
        ordering = ["-fecha", "-numero"]

    def __str__(self):
        return f"RC-{self.numero:05d} – {self.cliente} – ${self.monto_total}"

    @property
    def monto_total(self):
        return self.aplicaciones.aggregate(total=Sum("monto_aplicado"))["total"] or 0


class AplicacionRecibo(models.Model):
    recibo = models.ForeignKey(Recibo, on_delete=models.CASCADE, related_name="aplicaciones", verbose_name=_("Recibo"))
    factura = models.ForeignKey(FacturaVenta, on_delete=models.CASCADE, related_name="aplicaciones", verbose_name=_("Factura"))
    monto_aplicado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Monto aplicado"))

    class Meta:
        verbose_name = _("Aplicación de recibo")
        verbose_name_plural = _("Aplicaciones de recibo")

    def __str__(self):
        return f"${self.monto_aplicado} → {self.factura}"
