from modeltranslation.translator import register, TranslationOptions

from .models import TipoActividad, SubTipoActividad, CategoriaProducto


@register(TipoActividad)
class TipoActividadTranslationOptions(TranslationOptions):
    fields = ('nombre',)


@register(SubTipoActividad)
class SubTipoActividadTranslationOptions(TranslationOptions):
    fields = ('nombre',)


@register(CategoriaProducto)
class CategoriaProductoTranslationOptions(TranslationOptions):
    fields = ('nombre',)
