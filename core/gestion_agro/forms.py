from django import forms
from django.utils.translation import gettext as _
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User  
from django.utils import timezone
from django.forms import ModelForm
from agro.models import Ciudad
from gestion_agro.models import (Campo, Campana, CicloAgricola, Cultivo, ActividadProductiva,
                                 TipoActividad, SubTipoActividad, ActividadInsumo )


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

class CampoForm(BaseForm):
    class Meta:
        model = Campo
        fields = ["nombre", "ciudad", "superficie_ha", "descripcion", "image", "observaciones"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 2}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

class CampanaForm(BaseForm):
    class Meta:
        model = Campana
        exclude = ["empresa", "nombre"]
        widgets = {
            "fecha_desde": forms.DateInput(attrs={"type": "date"}),
            "fecha_hasta": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

class CicloForm(BaseForm):
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
           self.fields["fecha_inicio"].initial = timezone.localdate()

        if empresa:
            self.fields["campo"].queryset = Campo.objects.filter(empresa=empresa).order_by("nombre")
            self.fields["campana"].queryset = Campana.objects.filter(empresa=empresa).order_by("-fecha_desde")

            campana_activa = Campana.objects.filter(
                empresa=empresa,
                activa=True
            ).first()

            if campana_activa:
                self.fields["campana"].initial = campana_activa

    class Meta:
        model = CicloAgricola
        fields = ["campo", "campana", "cultivo", "superficie_ha", "fecha_inicio", "fecha_fin"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

class CicloFiltroForm(BaseSimpleForm):
    campana = forms.ModelChoiceField(queryset=None, required=False, empty_label="Todas", label="Campaña")
    campo = forms.ModelChoiceField(queryset=None, required=False, empty_label="Todos", label="Campo" )
    cultivo = forms.ModelChoiceField(queryset=None, required=False, empty_label="Todos", label="Cultivo")
    estado = forms.ChoiceField(choices=[("", "Todos"), ("activo", "Activo"), ("cerrado", "Cerrado"), ], required=False, label="Estado" )

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)

        if empresa:
            self.fields["campana"].queryset = Campana.objects.filter(empresa=empresa).order_by("-fecha_desde")
            self.fields["campo"].queryset = Campo.objects.filter(empresa=empresa).order_by("nombre")

        self.fields["cultivo"].queryset = Cultivo.objects.all().order_by("nombre")

class ActividadProductivaForm(BaseForm):

    class Meta:
        model = ActividadProductiva
        fields = [
            "fecha",
            "tipo",
            "subtipo",
            "observaciones",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["fecha"].label = _("Fecha")
        self.fields["tipo"].label = _("Tipo")
        self.fields["subtipo"].label = _("Subtipo")
        self.fields["observaciones"].label = _("Observaciones")

        # Tipos activos
        self.fields["tipo"].queryset = (
            TipoActividad.objects
            .filter(activo=True)
            .order_by("orden", "nombre")
        )

        # Subtipos vacíos al inicio
        self.fields["subtipo"].queryset = SubTipoActividad.objects.none()
        self.fields["subtipo"].required = False

        tipo_id = None

        # Si viene POST
        if "tipo" in self.data:
            try:
                tipo_id = int(self.data.get("tipo"))
            except (TypeError, ValueError):
                tipo_id = None

        # Si es edición
        elif self.instance.pk and self.instance.tipo_id:
            tipo_id = self.instance.tipo_id

        # Cargar subtipos del tipo
        if tipo_id:
            self.fields["subtipo"].queryset = (
                SubTipoActividad.objects
                .filter(tipo_actividad_id=tipo_id, activo=True)
                .order_by("nombre")
            )

    def clean(self):
        cleaned_data = super().clean()

        tipo = cleaned_data.get("tipo")
        subtipo = cleaned_data.get("subtipo")

        if tipo and subtipo:
            if subtipo.tipo_actividad_id != tipo.id:
                self.add_error(
                    "subtipo",
                    _("El subtipo no corresponde al tipo de actividad seleccionado.")
                )

        return cleaned_data
    
class ActividadInsumoForm(BaseForm):
    class Meta:
        model = ActividadInsumo
        fields = ["producto", "dosis", "um"]
        widgets = {
            "producto": forms.Select(),
            "dosis": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "um": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["producto"].label = _("Producto")
        self.fields["dosis"].label = _("Dosis")
        self.fields["um"].label = _("Unidad")

        self.fields["producto"].required = False
        self.fields["dosis"].required = False
        self.fields["um"].required = False

    def clean(self):
        cleaned_data = super().clean()

        producto = cleaned_data.get("producto")
        dosis = cleaned_data.get("dosis")
        um = cleaned_data.get("um")

        if self.cleaned_data.get("DELETE"):
            return cleaned_data

        hay_datos = bool(producto or dosis or um)

        if not hay_datos:
            return cleaned_data

        if not producto:
            self.add_error("producto", _("Debe seleccionar un producto."))

        if dosis in (None, ""):
            self.add_error("dosis", _("Debe ingresar la dosis."))

        if not um:
            self.add_error("um", _("Debe seleccionar la unidad."))

        return cleaned_data
    
ActividadInsumoFormSet = inlineformset_factory(
    ActividadProductiva,
    ActividadInsumo,
    form=ActividadInsumoForm,
    extra=1,
    can_delete=True
)
