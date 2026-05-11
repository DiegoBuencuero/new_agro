from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from gestion_agro.models import FacturaCompra, Proveedor, Cliente, EntregaDepositoExterno
from agro.models import Empresa


class Pago(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, verbose_name=_("Proveedor"))
    fecha = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha"))
    observaciones = models.TextField(blank=True, null=True, verbose_name=_("Observaciones"))

    class Meta:
        verbose_name = _("Pago")
        verbose_name_plural = _("Pagos")
        ordering = ["-fecha"]

    def __str__(self):
        return f"Pago {self.id} – {self.proveedor} – ${self.monto_total}"

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


class FacturaVenta(models.Model):
    empresa  = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    cliente  = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name=_("Cliente"))
    entrega  = models.ForeignKey(
        EntregaDepositoExterno,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="facturas_venta",
        verbose_name=_("Entrega depósito externo"),
    )
    nfe_numero        = models.CharField(max_length=20, verbose_name=_("NF-e número"))
    nfe_serie         = models.CharField(max_length=5, default="1", verbose_name=_("Serie"))
    fecha             = models.DateField(verbose_name=_("Fecha"))
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name=_("Fecha vencimiento"))
    total             = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Total"))
    archivo_pdf       = models.FileField(upload_to="facturas_venta/", blank=True, null=True, verbose_name=_("PDF"))
    creada            = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Factura de venta")
        verbose_name_plural = _("Facturas de venta")
        unique_together = ("empresa", "cliente", "nfe_numero")
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.cliente} – {self.nfe_numero}"


class FacturaVentaItem(models.Model):
    factura        = models.ForeignKey(FacturaVenta, on_delete=models.CASCADE, related_name="items", verbose_name=_("Factura"))
    descripcion    = models.CharField(max_length=255, verbose_name=_("Descripción"))
    cantidad       = models.DecimalField(max_digits=12, decimal_places=3, verbose_name=_("Cantidad (kg)"))
    precio_unitario= models.DecimalField(max_digits=14, decimal_places=4, verbose_name=_("Precio unitario"))
    subtotal       = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Subtotal"))

    class Meta:
        verbose_name = _("Ítem de factura de venta")
        verbose_name_plural = _("Ítems de factura de venta")

    def __str__(self):
        return f"{self.descripcion} – {self.cantidad} kg"


class Cobro(models.Model):
    empresa      = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    cliente      = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name=_("Cliente"))
    fecha        = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha"))
    observaciones= models.TextField(blank=True, null=True, verbose_name=_("Observaciones"))

    class Meta:
        verbose_name = _("Cobro")
        verbose_name_plural = _("Cobros")
        ordering = ["-fecha"]

    def __str__(self):
        return f"Cobro {self.id} – {self.cliente} – ${self.monto_total}"

    @property
    def monto_total(self):
        return self.aplicaciones.aggregate(total=Sum("monto_aplicado"))["total"] or 0


class AplicacionCobro(models.Model):
    cobro          = models.ForeignKey(Cobro, on_delete=models.CASCADE, related_name="aplicaciones", verbose_name=_("Cobro"))
    factura        = models.ForeignKey(FacturaVenta, on_delete=models.CASCADE, related_name="aplicaciones", verbose_name=_("Factura"))
    monto_aplicado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Monto aplicado"))

    class Meta:
        verbose_name = _("Aplicación de cobro")
        verbose_name_plural = _("Aplicaciones de cobro")

    def __str__(self):
        return f"${self.monto_aplicado} → {self.factura}"
