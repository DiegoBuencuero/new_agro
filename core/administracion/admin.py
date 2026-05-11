from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Pago, AplicacionPago,
    FacturaVenta, FacturaVentaItem,
    Cobro, AplicacionCobro,
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
    list_display = ["id", "empresa", "cliente", "nfe_numero", "nfe_serie", "fecha", "fecha_vencimiento", "total"]
    list_filter = ["empresa", "cliente", "fecha"]
    search_fields = ["nfe_numero", "cliente__nombre"]
    date_hierarchy = "fecha"
    inlines = [FacturaVentaItemInline]


class AplicacionCobroInline(admin.TabularInline):
    model = AplicacionCobro
    extra = 1
    autocomplete_fields = ["factura"]


@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = ["id", "empresa", "cliente", "monto_total", "fecha"]
    list_filter = ["empresa", "cliente"]
    search_fields = ["cliente__nombre", "observaciones"]
    readonly_fields = ["fecha", "monto_total"]
    inlines = [AplicacionCobroInline]
