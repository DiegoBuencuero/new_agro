from django.contrib import admin
from django.urls import path, include
from agro.views import index,login_page
from gestion_agro.views import (vista_crear_campo, vista_editar_campo, vista_crear_campana, vista_editar_campana,vista_crear_ciclo,
vista_lista_ciclos, vista_detalle_ciclo, vista_editar_ciclo, ajax_get_ciclos_data, vista_agregar_actividad,
 ajax_subtipos_tipo_actividad, ajax_productos_por_actividad               
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    path('i18n/', include('django.conf.urls.i18n')), 

    path('login/', login_page, name='login'),
    # path('signup/', signup, name='signup'),
    # path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('campos/', vista_crear_campo, name='vista_crear_campo'),
    path('campos/<int:id_campo>/', vista_editar_campo, name='vista_editar_campo'),

    path('campanas/', vista_crear_campana, name='vista_crear_campana'),
    path('campanas/<int:id_campana>/', vista_editar_campana, name='vista_editar_campana'),

    path('ciclos/', vista_lista_ciclos, name='vista_lista_ciclos'),
    path('ciclos/nuevo/', vista_crear_ciclo, name='vista_crear_ciclo'),
    path('ajax/get_ciclos_data/', ajax_get_ciclos_data, name="ajax_get_ciclos_data"),
    path('ciclos/<int:id_ciclo>/', vista_detalle_ciclo, name='vista_detalle_ciclo'),
    path('ciclo/<int:id_ciclo>/actividad/nueva/', vista_agregar_actividad, name="vista_agregar_actividad"),
    path("ajax/subtipos-tipo-actividad/", ajax_subtipos_tipo_actividad, name="ajax_subtipos_tipo_actividad" ),
    path("ajax/productos-por-actividad/", ajax_productos_por_actividad, name="ajax_productos_por_actividad"),

]
