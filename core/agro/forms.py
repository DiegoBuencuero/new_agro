from django import forms
from django.utils.translation import gettext as _
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User  
from django.forms import ModelForm
from agro.models import Pais, Profile


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