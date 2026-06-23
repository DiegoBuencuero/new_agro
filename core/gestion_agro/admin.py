from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from agro.models import Profile, Pais, Provincia, Ciudad, Empresa, Moneda, Unidad, ConversionUM
from gestion_agro.models import ( Campo, Lote, Actividad, Cultivo, Variedad, Campana,
    CicloAgricola, FaseAgricola, TipoActividad, 
    SubTipoActividad, ActividadProductiva, CamposVistoria, CamposCosecha, CategoriaProducto,
    Producto, ProductoSemilla, ActividadInsumo, ProductoNormalizado, PresentacionProducto,
    Proveedor, FacturaCompra, FacturaCompraItem, MovimientoStock, TipoActividadCategoriaProducto,
    Cliente
)


admin.site.register(Profile)
admin.site.register(Pais)
admin.site.register(Provincia)
admin.site.register(Ciudad)
admin.site.register(Empresa)
admin.site.register(Moneda)
admin.site.register(Unidad)
admin.site.register(ConversionUM)

admin.site.register(TipoActividadCategoriaProducto)


@admin.register(Campo)
class CampoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "ciudad", "superficie_ha")
    search_fields = ("nombre", "empresa__nombre", "ciudad__nombre")
    list_filter = ("empresa", "ciudad")


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "campo", "ha_totales", "ha_productivas")
    search_fields = ("nombre", "campo__nombre")
    list_filter = ("campo",)


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo")
    search_fields = ("nombre", "codigo")


@admin.register(Cultivo)
class CultivoAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(Variedad)
class VariedadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cultivo")
    search_fields = ("nombre", "cultivo__nombre")
    list_filter = ("cultivo",)


@admin.register(Campana)
class CampanaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "fecha_desde", "fecha_hasta", "activa")
    search_fields = ("nombre", "empresa__nombre")
    list_filter = ("empresa", "activa")


@admin.register(CicloAgricola)
class CicloAgricolaAdmin(admin.ModelAdmin):
    list_display = ("nombre_lote", "campo", "campana", "cultivo", "superficie_ha", "fecha_inicio", "fecha_fin", "activa")
    search_fields = ("nombre_lote", "campo__nombre", "campana__nombre", "cultivo__nombre")
    list_filter = ("activa", "campo", "campana", "cultivo")


@admin.register(FaseAgricola)
class FaseAgricolaAdmin(admin.ModelAdmin):
    list_display = ("ciclo", "tipo", "fecha_inicio", "fecha_fin", "estado")
    search_fields = ("ciclo__nombre_lote",)
    list_filter = ("tipo", "estado")


@admin.register(ActividadProductiva)
class ActividadProductivaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "subtipo", "fase")
    search_fields = ("tipo__nombre", "subtipo__nombre", "fase__ciclo__nombre_lote")
    list_filter = ("tipo", "subtipo", "fecha")


@admin.register(CamposVistoria)
class CamposVistoriaAdmin(admin.ModelAdmin):
    list_display = ("actividad", "plantas_m2", "malezas", "insectos", "enfermedades")
    search_fields = ("actividad__tipo__nombre", "actividad__fase__ciclo__nombre_lote")


@admin.register(CamposCosecha)
class CamposCosechaAdmin(admin.ModelAdmin):
    list_display = ("actividad", "rendimiento")
    search_fields = ("actividad__tipo__nombre", "actividad__fase__ciclo__nombre_lote")


@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(TranslationAdmin):
    list_display = ("codigo", "nombre")
    search_fields = ("codigo", "nombre")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa", "categoria", "unidad_base", "maneja_stock", "activo")
    search_fields = ("codigo", "nombre", "empresa__nombre")
    list_filter = ("empresa", "categoria", "unidad_base", "maneja_stock", "activo")


@admin.register(ProductoSemilla)
class ProductoSemillaAdmin(admin.ModelAdmin):
    list_display = ("producto", "cultivo", "variedad")
    search_fields = ("producto__nombre", "cultivo__nombre", "variedad__nombre")
    list_filter = ("cultivo", "variedad")


@admin.register(ActividadInsumo)
class ActividadInsumoAdmin(admin.ModelAdmin):
    list_display = ("actividad", "producto", "dosis", "um", "cantidad_real", "costo_total", "costo_ha")
    search_fields = ("actividad__tipo__nombre", "producto__nombre")
    list_filter = ("um",)


@admin.register(ProductoNormalizado)
class ProductoNormalizadoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "envase_tipo", "contenido_cantidad", "contenido_unidad", "precio_envase", "fecha_importacion")
    search_fields = ("nombre", "origen_descripcion", "origen_codigo")
    list_filter = ("empresa", "envase_tipo", "unidad_estandar", "fecha_importacion")


@admin.register(PresentacionProducto)
class PresentacionProductoAdmin(admin.ModelAdmin):
    list_display = ("producto", "nombre", "unidad_factura", "contenido", "unidad_contenido")
    search_fields = ("producto__nombre", "nombre")
    list_filter = ("unidad_contenido",)


@admin.register(Proveedor)
class ProveedorAgroAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "empresa", "identificador")
    search_fields = ("razon_social", "identificador")
    list_filter = ("empresa",)


class FacturaCompraItemInline(admin.TabularInline):
    model = FacturaCompraItem
    extra = 0


@admin.register(FacturaCompra)
class FacturaCompraAdmin(admin.ModelAdmin):
    list_display = ("numero", "empresa", "proveedor", "fecha", "total")
    search_fields = ("numero", "proveedor__razon_social")
    list_filter = ("empresa", "proveedor", "fecha")
    inlines = [FacturaCompraItemInline]


@admin.register(FacturaCompraItem)
class FacturaCompraItemAdmin(admin.ModelAdmin):
    list_display = ("factura", "producto", "presentacion", "cantidad_facturada", "cantidad_base", "precio_unitario", "subtotal")
    search_fields = ("factura__numero", "producto__nombre")
    list_filter = ("presentacion",)


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("producto", "tipo", "destino", "cantidad", "fecha", "deposito_origen", "deposito_destino", "factura_item", "actividad_item")
    search_fields = ("producto__nombre",)
    list_filter = ("tipo", "destino", "fecha")


@admin.register(TipoActividad)
class TipoActividadAdmin(TranslationAdmin):
    list_display = (
        "nombre",
        "tipo",
        "activo",
        "requiere_subtipo",
        "requiere_insumo",
        "requiere_mo",
        "requiere_maq",
        "requiere_vist",
        "requiere_cosecha",
    )
    list_filter = ("activo", "requiere_subtipo", "tipo")
    search_fields = ("nombre",)


@admin.register(SubTipoActividad)
class SubTipoActividadAdmin(TranslationAdmin):
    list_display = ("nombre", "codigo", "tipo_actividad", "activo")
    list_filter = ("activo", "tipo_actividad")
    search_fields = ("nombre", "codigo")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "identificador", "empresa")
    search_fields = ("razon_social", "identificador")
    list_filter = ("empresa",)