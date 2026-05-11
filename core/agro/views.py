from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib import messages
from django.db import transaction
from .forms import LoginForm, ConfiguracionEmpresaForm, RegistroForm


def login_page(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'GET':
        form = LoginForm()
        return render(request, 'login.html', {'form': form})

    form = LoginForm(request.POST)
    if form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect('/')

    messages.error(request, _('Usuario o contraseña incorrectos'))
    return render(request, 'login.html', {'form': form})



def index(request):
    return render(request, "index.html")


def vista_registro(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                from agro.models import Moneda
                moneda = Moneda.objects.first()
                if not moneda:
                    messages.error(request, _("El sistema no tiene monedas configuradas. Contacte al administrador."))
                    return render(request, "registro.html", {"form": form})

                with transaction.atomic():
                    from agro.models import Empresa
                    empresa = Empresa.objects.create(
                        nombre=cd["empresa_nombre"],
                        razon_social=cd["empresa_razon_social"],
                        cuit=cd["empresa_cuit"],
                        moneda=moneda,
                        status="O",
                    )
                    from django.contrib.auth.models import User
                    user = User.objects.create_user(
                        username=cd["username"],
                        email=cd["email"],
                        password=cd["password1"],
                    )
                    user.profile.empresa = empresa
                    user.profile.tipo = "A"
                    user.profile.status = "A"
                    user.profile.save()

                messages.success(request, _("Cuenta creada correctamente. Podés ingresar ahora."))
                return redirect("login")
            except Exception:
                messages.error(request, _("Error al crear la cuenta. Intentá nuevamente."))
    else:
        form = RegistroForm()

    return render(request, "registro.html", {"form": form})


def vista_cuenta_suspendida(request):
    return render(request, "cuenta_suspendida.html")


@login_required
def vista_configuracion(request):
    empresa = request.user.profile.empresa

    if request.method == "POST":
        form = ConfiguracionEmpresaForm(empresa, request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, _("Configuración guardada correctamente"))
            return redirect("vista_configuracion")
        else:
            messages.error(request, _("Corrija los errores del formulario"))
    else:
        form = ConfiguracionEmpresaForm(empresa, instance=empresa)

    return render(request, "configuracion.html", {"form": form, "empresa": empresa})