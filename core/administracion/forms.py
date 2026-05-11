from decimal import Decimal
from django import forms
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from gestion_agro.models import Proveedor, FacturaCompra
from .models import AplicacionPago


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
