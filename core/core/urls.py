"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from agro.views import index,login_page
from gestion_agro.views import (vista_campos, editar_campos, vista_campanas, editar_campana,vista_crear_ciclo,
vista_lista_ciclo                             
)
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    path('i18n/', include('django.conf.urls.i18n')), 

    path('login/', login_page, name='login'),
    # path('signup/', signup, name='signup'),
    # path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('campos/', vista_campos, name='vista_campos'),
    path('campos/<int:id_campo>/', editar_campos, name='editar_campos'),
    path('campanas/', vista_campanas, name='vista_campanas'),
    path('campana/<int:id_campana>/', editar_campana, name='editar_campana'),
    path("ciclo/nueva/", vista_crear_ciclo, name="vista_crear_ciclo"),
    path("ciclos/", vista_lista_ciclo, name="vista_lista_ciclo"),

]
