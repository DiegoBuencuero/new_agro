from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Pago, AplicacionPago,
    FacturaVenta, FacturaVentaItem,
    Recibo, AplicacionRecibo,
)


class AplicacionPagoInline(admin.TabularInline):
    model = AplicacionPago
    extra = 1
    autocomplete_fields = ["factura"]


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ["id", "empresa", "proveedor", "monto_total", "fecha"]
    list_filter = ["empresa", "proveedor"]
    search_fields = ["proveedor__nombre", "observaciones"]
    readonly_fields = ["fecha", "monto_total"]
    inlines = [AplicacionPagoInline]


class FacturaVentaItemInline(admin.TabularInline):
    model = FacturaVentaItem
    extra = 1


@admin.register(FacturaVenta)
class FacturaVentaAdmin(admin.ModelAdmin):
    list_display = ["id", "empresa", "cliente", "numero", "fecha", "fecha_vencimiento"]
    list_filter = ["empresa", "cliente", "fecha"]
    search_fields = ["numero", "cliente__nombre"]
    date_hierarchy = "fecha"
    inlines = [FacturaVentaItemInline]


class AplicacionReciboInline(admin.TabularInline):
    model = AplicacionRecibo
    extra = 1
    autocomplete_fields = ["factura"]


@admin.register(Recibo)
class ReciboAdmin(admin.ModelAdmin):
    list_display = ["id", "empresa", "cliente", "monto_total", "fecha"]
    list_filter = ["empresa", "cliente"]
    search_fields = ["cliente__nombre", "observaciones"]
    readonly_fields = ["fecha", "monto_total"]
    inlines = [AplicacionReciboInline]
