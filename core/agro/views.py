from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib import messages
from .forms import LoginForm


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