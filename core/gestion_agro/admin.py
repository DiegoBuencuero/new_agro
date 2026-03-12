from django.contrib import admin
from agro.models import Profile, Pais, Provincia, Ciudad, Empresa, Moneda
from gestion_agro.models import Campo, CicloAgricola, Campana, Cultivo

admin.site.register(Profile)
admin.site.register(Pais)
admin.site.register(Provincia)
admin.site.register(Ciudad)
admin.site.register(Campo)
admin.site.register(CicloAgricola)
admin.site.register(Empresa)
admin.site.register(Campana)
admin.site.register(Moneda)
admin.site.register(Cultivo)
