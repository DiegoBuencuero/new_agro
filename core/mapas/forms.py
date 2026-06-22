from django import forms
from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _

from gestion_agro.models import AreaCampo, Campo, CicloAgricola
from mapas.models import MedicionCampo


class BaseForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(BaseForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class BaseSimpleForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(BaseSimpleForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class CapaMapaForm(BaseSimpleForm):

    nombre = forms.CharField(max_length=100, label=_("Nombre"))
    campo = forms.ModelChoiceField(queryset=Campo.objects.none(), label=_("Campo"))
    ciclo = forms.ModelChoiceField(queryset=CicloAgricola.objects.none(), label=_("Ciclo"), required=False)
    area = forms.ModelChoiceField(queryset=AreaCampo.objects.none(), label=_("Área"), required=False)
    fecha = forms.DateField(label=_("Fecha"), widget=forms.DateInput(attrs={"type":"date"}))

    archivo = forms.FileField(label=_("Archivo"), widget=forms.FileInput(attrs={"accept":".zip,.shp,.dbf,.shx,.prj,.kml,.kmz,.geojson,.json"}))

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields["campo"].queryset = Campo.objects.filter(empresa=empresa).order_by("nombre")


class LluviaForm(BaseForm):
    class Meta:
        model  = MedicionCampo
        fields = ["campo", "fecha", "promedio"]
        labels = {
            "campo":    _("Campo"),
            "fecha":    _("Fecha"),
            "promedio": _("Precipitación (mm)"),
        }
        widgets = {
            "fecha":    forms.DateInput(attrs={"type": "date"}),
            "promedio": forms.NumberInput(attrs={"step": "0.1", "min": "0"}),
        }

    def __init__(self, empresa=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields["campo"].queryset = Campo.objects.filter(empresa=empresa).order_by("nombre")
        self.fields["campo"].widget.attrs["class"]    = "form-select"
        self.fields["fecha"].widget.attrs["class"]    = "form-control"
        self.fields["promedio"].widget.attrs["class"] = "form-control"