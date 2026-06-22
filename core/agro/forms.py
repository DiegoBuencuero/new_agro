from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _

from agro.models import Empresa, Unidad
from gestion_agro.models import Deposito


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


class RegistroForm(BaseSimpleForm):
    empresa_nombre = forms.CharField(label=_("Nombre de la empresa"), max_length=100, widget=forms.TextInput(attrs={"placeholder": _("Ej: Estancia San Juan")}))
    empresa_razon_social = forms.CharField(label=_("Razón social"), max_length=100)
    empresa_cuit = forms.CharField(label=_("CUIT / CNPJ"), max_length=50, widget=forms.TextInput(attrs={"placeholder": "00.000.000/0000-00"}))

    username = forms.CharField(label=_("Usuario"), max_length=150, widget=forms.TextInput(attrs={"placeholder": _("Sin espacios")}))
    email = forms.EmailField(label=_("Email"))
    password1 = forms.CharField(label=_("Contraseña"), min_length=8, widget=forms.PasswordInput())
    password2 = forms.CharField(label=_("Confirmar contraseña"), widget=forms.PasswordInput())

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise ValidationError(_("Ese nombre de usuario ya está en uso."))
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("Ya existe una cuenta con ese email."))
        return email

    def clean(self):
        cd = super().clean()
        if cd.get("password1") != cd.get("password2"):
            self.add_error("password2", _("Las contraseñas no coinciden."))
        return cd


class ConfiguracionEmpresaForm(ModelForm):
    class Meta:
        model = Empresa
        fields = [
            "valor_mobra",
            "valor_maquina",
            "calculo_costo",
            "deposito_insumos_default",
            "deposito_producto_final_default",
            "unidad_inspeccion_semilla",
        ]
        widgets = {
            "valor_mobra":                    forms.NumberInput(attrs={"class": "form-control"}),
            "valor_maquina":                  forms.NumberInput(attrs={"class": "form-control"}),
            "calculo_costo":                  forms.Select(attrs={"class": "form-control"}),
            "deposito_insumos_default":       forms.Select(attrs={"class": "form-control"}),
            "deposito_producto_final_default":forms.Select(attrs={"class": "form-control"}),
            "unidad_inspeccion_semilla":      forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, empresa, *args, **kwargs):
        super().__init__(*args, **kwargs)
        depositos = Deposito.objects.filter(empresa=empresa)
        self.fields["deposito_insumos_default"].queryset = depositos
        self.fields["deposito_producto_final_default"].queryset = depositos
        self.fields["deposito_insumos_default"].required = False
        self.fields["deposito_producto_final_default"].required = False
        self.fields["unidad_inspeccion_semilla"].queryset = Unidad.objects.all().order_by("nombre")
        self.fields["unidad_inspeccion_semilla"].required = False


class LoginForm(BaseSimpleForm):
    username = forms.CharField(
        label=_("Usuario"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Usuario")
        })
    )

    password = forms.CharField(
        label=_("Contraseña"),
        widget=forms.PasswordInput(attrs={
            "placeholder": _("Contraseña")
        })
    )