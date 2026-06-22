from decimal import Decimal
from django import forms
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from django.forms import formset_factory

from gestion_agro.models import DESTINO_CHOICES, Proveedor, FacturaCompra, Cliente, Deposito, Producto
from agro.models import Unidad
from .models import AplicacionPago, FacturaVenta, FacturaVentaItem, AplicacionRecibo


class FacturaVentaForm(forms.ModelForm):
    class Meta:
        model = FacturaVenta
        fields = ["numero", "cliente", "fecha", "fecha_vencimiento"]
        widgets = {
            "numero":           forms.TextInput(attrs={"class": "form-control"}),
            "cliente":          forms.Select(attrs={"class": "form-select"}),
            "fecha":            forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "fecha_vencimiento":forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, empresa=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields["cliente"].queryset = Cliente.objects.filter(empresa=empresa).order_by("razon_social")
        self.fields["fecha_vencimiento"].required = False


class FacturaVentaItemForm(forms.ModelForm):
    class Meta:
        model = FacturaVentaItem
        fields = ["cantidad", "precio_unitario", "deposito_origen", "um"]
        widgets = {
            "cantidad":       forms.NumberInput(attrs={"class": "form-control", "step": "0.001", "min": "0.001"}),
            "precio_unitario":forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "deposito_origen":forms.Select(attrs={"class": "form-select"}),
            "um":             forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, empresa=None, producto=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields["deposito_origen"].queryset = Deposito.objects.filter(empresa=empresa)
        if producto:
            self.fields["um"].queryset = Unidad.objects.filter(
                id=producto.unidad_base_id
            ) | Unidad.objects.filter(
                conversiones_origen__um_destino=producto.unidad_base
            )
            self.fields["um"].initial = producto.unidad_base_id
        self.fields["deposito_origen"].required = False


class AplicacionReciboForm(forms.ModelForm):
    class Meta:
        model  = AplicacionRecibo
        fields = ["factura", "monto_aplicado"]

    def __init__(self, empresa=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields["factura"].queryset = FacturaVenta.objects.filter(empresa=empresa)

    def clean(self):
        cd      = super().clean()
        factura = cd.get("factura")
        monto   = cd.get("monto_aplicado")
        if not factura or not monto:
            return cd
        total   = sum(i.cantidad * i.precio_unitario for i in factura.items.all())
        cobrado = factura.aplicaciones.aggregate(
            t=Coalesce(Sum("monto_aplicado"), Decimal("0"))
        )["t"]
        saldo = total - cobrado
        if monto <= 0:
            raise forms.ValidationError(_("El monto debe ser mayor a 0."))
        if monto > saldo:
            raise forms.ValidationError(
                _("El monto $%(m)s supera el saldo disponible $%(s)s.") % {"m": monto, "s": saldo}
            )
        return cd


class FiltroFacturasForm(forms.Form):
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.none(),
        required=False,
        label=_("Proveedor"),
        empty_label=_("Todos los proveedores"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    fecha_desde = forms.DateField(
        required=False,
        label=_("Fecha desde"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label=_("Fecha hasta"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, empresa, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(empresa=empresa).order_by("razon_social")


class AplicacionPagoForm(forms.ModelForm):
    """
    Valida un ítem del pago: factura + monto.
    La validación del saldo vive aquí, no en la vista.
    Requiere empresa para restringir el queryset de facturas.
    """

    class Meta:
        model = AplicacionPago
        fields = ["factura", "monto_aplicado"]

    def __init__(self, empresa=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields["factura"].queryset = FacturaCompra.objects.filter(empresa=empresa)

    def clean(self):
        cd      = super().clean()
        factura = cd.get("factura")
        monto   = cd.get("monto_aplicado")

        if not factura or not monto:
            return cd

        pagado = factura.aplicaciones.aggregate(
            total=Coalesce(Sum("monto_aplicado"), Decimal("0"))
        )["total"]
        saldo = factura.total - pagado

        if monto <= 0:
            raise forms.ValidationError(
                _("El monto debe ser mayor a 0 (factura %(num)s)") % {"num": factura.numero}
            )
        if monto > saldo:
            raise forms.ValidationError(
                _("Factura %(num)s: el monto $%(monto)s supera el saldo disponible $%(saldo)s") % {
                    "num": factura.numero,
                    "monto": monto,
                    "saldo": saldo,
                }
            )
        return cd


class FacturaVentaManualForm(forms.ModelForm):
    class Meta:
        model = FacturaVenta
        fields = ["cliente", "numero", "fecha", "fecha_vencimiento"]
        widgets = {
            "cliente":           forms.Select(attrs={"class": "form-select form-select-sm"}),
            "numero":            forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "fecha":             forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
            "fecha_vencimiento": forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
        }

    def __init__(self, empresa=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields["cliente"].queryset = Cliente.objects.filter(empresa=empresa).order_by("razon_social")
        self.fields["fecha_vencimiento"].required = False


class ProductoFinalChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        try:
            ds = obj.datos_semilla
            return f"{ds.cultivo.nombre} {ds.variedad.nombre}"
        except Exception:
            return obj.nombre


class FacturaVentaManualItemForm(forms.Form):
    producto = ProductoFinalChoiceField(
        queryset=Producto.objects.none(),
        required=True,
        empty_label="— Seleccionar —",
        label=_("Producto"),
    )
    destino = forms.ChoiceField(
        choices=[("", _("— Sin especificar —"))] + list(DESTINO_CHOICES),
        required=False,
        label=_("Destino"),
    )
    deposito_origen = forms.ModelChoiceField(
        queryset=Deposito.objects.none(),
        required=False,
        empty_label="— Sin filtro —",
        label=_("Depósito origen"),
    )
    cantidad = forms.DecimalField(
        min_value=Decimal("0.001"), decimal_places=3,
        label=_("Cantidad"),
        widget=forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
    )
    precio_unitario = forms.DecimalField(
        min_value=0, decimal_places=2,
        label=_("Precio unit."),
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    )
    subtotal = forms.DecimalField(
        required=False, decimal_places=2,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa

        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.HiddenInput):
                continue
            if isinstance(w, forms.Select):
                w.attrs["class"] = "form-select form-select-sm"
            else:
                w.attrs["class"] = "form-control form-control-sm"

        if empresa:
            self.fields["producto"].queryset = (
                Producto.objects
                .filter(empresa=empresa, activo=True, producto_final=True)
                .select_related("categoria", "datos_semilla__cultivo", "datos_semilla__variedad")
                .order_by("nombre")
            )
            self.fields["deposito_origen"].queryset = (
                Deposito.objects.filter(empresa=empresa).order_by("nombre")
            )

    def clean(self):
        cleaned = super().clean()
        cantidad = cleaned.get("cantidad") or Decimal("0")
        precio = cleaned.get("precio_unitario") or Decimal("0")
        cleaned["subtotal"] = cantidad * precio
        return cleaned


FacturaVentaManualItemFormSet = formset_factory(FacturaVentaManualItemForm, extra=1)
