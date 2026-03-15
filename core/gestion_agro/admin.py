from django.contrib import admin
from agro.models import Profile, Pais, Provincia, Ciudad, Empresa, Moneda
from gestion_agro.models import (Campo, CicloAgricola, Campana, Cultivo, FaseAgricola, 
                                ActividadProductiva, TipoActividad,  SubTipoActividad, )


admin.site.register(Profile)
admin.site.register(Pais)
admin.site.register(Provincia)
admin.site.register(Ciudad)

admin.site.register(Empresa)
admin.site.register(Moneda)

admin.site.register(Campo)
admin.site.register(Campana)
admin.site.register(Cultivo)

admin.site.register(CicloAgricola)
admin.site.register(FaseAgricola)

admin.site.register(TipoActividad)
admin.site.register(SubTipoActividad)

admin.site.register(ActividadProductiva)