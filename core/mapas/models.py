from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from gestion_agro.models import Campo, AreaCampo, CicloAgricola


class VariableAnalitica(models.Model):
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre"))
    unidad = models.CharField(max_length=30, blank=True, verbose_name=_("Unidad"))
    tipo = models.CharField(
        max_length=20,
        choices=[
            ("satelite", "Satélite"),
            ("suelo", "Análisis de suelo"),
            ("cosecha", "Rendimiento / Cosecha"),
            ("otro", "Otro"),
        ],
        verbose_name=_("Tipo"),
    )
    rango_minimo = models.FloatField(null=True, blank=True, verbose_name=_("Rango mínimo esperado"))
    rango_maximo = models.FloatField(null=True, blank=True, verbose_name=_("Rango máximo esperado"))

    class Meta:
        verbose_name = _("Variable analítica")
        verbose_name_plural = _("Variables analíticas")
        ordering = ["tipo", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.unidad})" if self.unidad else self.nombre


class CapturaSatelite(models.Model):
    campo = models.ForeignKey(
        Campo, on_delete=models.CASCADE,
        related_name="capturas_satelite", verbose_name=_("Campo"),
    )
    ciclo = models.ForeignKey(
        CicloAgricola, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="capturas_satelite", verbose_name=_("Ciclo agrícola"),
    )
    area_campo = models.ForeignKey(
        AreaCampo, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="capturas_satelite", verbose_name=_("Área del campo"),
    )
    fecha = models.DateField(verbose_name=_("Fecha de imagen"))
    fuente = models.CharField(
        max_length=20,
        choices=[
            ("sentinel2", "Sentinel-2"),
            ("landsat", "Landsat"),
            ("manual", "Manual"),
        ],
        default="sentinel2",
        verbose_name=_("Fuente"),
    )
    nubosidad_pct = models.FloatField(default=0, verbose_name=_("% Nubosidad"))
    estado = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("procesada", "Procesada"),
            ("error", "Error"),
        ],
        default="pendiente",
        verbose_name=_("Estado"),
    )
    fecha_procesado = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha procesado"))

    class Meta:
        verbose_name = _("Captura satelital")
        verbose_name_plural = _("Capturas satelitales")
        ordering = ["-fecha"]
        unique_together = [("campo", "area_campo", "fecha", "fuente")]

    def __str__(self):
        return f"{self.campo.nombre} — {self.fecha} ({self.fuente})"


class IndiceVegetacion(models.Model):
    captura = models.ForeignKey(
        CapturaSatelite, on_delete=models.CASCADE,
        related_name="indices", verbose_name=_("Captura"),
    )
    tipo = models.CharField(
        max_length=10,
        choices=[
            ("ndvi", "NDVI"),
            ("evi", "EVI"),
            ("ndre", "NDRE"),
            ("savi", "SAVI"),
        ],
        verbose_name=_("Tipo de índice"),
    )
    promedio = models.FloatField(verbose_name=_("Promedio"))
    minimo = models.FloatField(verbose_name=_("Mínimo"))
    maximo = models.FloatField(verbose_name=_("Máximo"))
    grilla_datos = models.JSONField(null=True, blank=True, verbose_name=_("Grilla de datos (píxeles)"))
    imagen_png = models.ImageField(
        upload_to="indices/imagenes/", null=True, blank=True,
        verbose_name=_("Imagen PNG"),
    )
    geojson_file = models.FileField(
        upload_to="indices/geojson/", null=True, blank=True,
        verbose_name=_("GeoJSON"),
    )

    class Meta:
        verbose_name = _("Índice de vegetación")
        verbose_name_plural = _("Índices de vegetación")
        unique_together = [("captura", "tipo")]

    def __str__(self):
        return f"{self.tipo.upper()} — {self.captura}"


class ArchivoAnalitico(models.Model):
    campo = models.ForeignKey(
        Campo, on_delete=models.CASCADE,
        related_name="archivos_analiticos", verbose_name=_("Campo"),
    )
    ciclo = models.ForeignKey(
        CicloAgricola, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="archivos_analiticos", verbose_name=_("Ciclo agrícola"),
    )
    area_campo = models.ForeignKey(
        AreaCampo, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="archivos_analiticos", verbose_name=_("Área del campo"),
    )
    variable = models.ForeignKey(
        VariableAnalitica, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="archivos", verbose_name=_("Variable analítica"),
    )
    cargado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_("Cargado por"),
    )
    archivo = models.FileField(upload_to="archivos_analiticos/", verbose_name=_("Archivo"))
    tipo_archivo = models.CharField(
        max_length=20,
        choices=[
            ("shapefile", "Shapefile (.zip)"),
            ("geojson", "GeoJSON"),
            ("tif", "GeoTIFF"),
            ("csv", "CSV"),
        ],
        verbose_name=_("Tipo de archivo"),
    )
    estado = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("procesado", "Procesado"),
            ("error", "Error"),
        ],
        default="pendiente",
        verbose_name=_("Estado"),
    )
    fecha_carga = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de carga"))

    # Generados al procesar (rasterización PNG)
    imagen_png   = models.FileField(upload_to="archivos_analiticos/png/", null=True, blank=True)
    bbox         = models.JSONField(null=True, blank=True)       # [min_lng, min_lat, max_lng, max_lat]
    leyenda      = models.JSONField(null=True, blank=True)       # [{rango, color}, ...]
    estadisticas = models.JSONField(null=True, blank=True)       # {min, max, prom, std}

    class Meta:
        verbose_name = _("Archivo analítico")
        verbose_name_plural = _("Archivos analíticos")
        ordering = ["-fecha_carga"]

    def __str__(self):
        return f"{self.campo.nombre} — {self.archivo.name}"


class MedicionCampo(models.Model):
    campo = models.ForeignKey(
        Campo, on_delete=models.CASCADE,
        related_name="mediciones", verbose_name=_("Campo"),
    )
    ciclo = models.ForeignKey(
        CicloAgricola, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="mediciones", verbose_name=_("Ciclo agrícola"),
    )
    area_campo = models.ForeignKey(
        AreaCampo, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="mediciones", verbose_name=_("Área del campo"),
    )
    variable = models.ForeignKey(
        VariableAnalitica, on_delete=models.CASCADE,
        related_name="mediciones", verbose_name=_("Variable"),
    )
    fuente = models.ForeignKey(
        ArchivoAnalitico, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="mediciones", verbose_name=_("Archivo origen"),
    )
    fecha = models.DateField(verbose_name=_("Fecha"))
    promedio = models.FloatField(verbose_name=_("Promedio"))
    minimo = models.FloatField(null=True, blank=True, verbose_name=_("Mínimo"))
    maximo = models.FloatField(null=True, blank=True, verbose_name=_("Máximo"))

    class Meta:
        verbose_name = _("Medición de campo")
        verbose_name_plural = _("Mediciones de campo")
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.campo.nombre} — {self.variable.nombre} — {self.fecha}"


class CapaMapa(models.Model):
    campo = models.ForeignKey(
        Campo, on_delete=models.CASCADE,
        related_name="capas_mapa", verbose_name=_("Campo"),
    )
    ciclo = models.ForeignKey(
        CicloAgricola, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="capas_mapa", verbose_name=_("Ciclo agrícola"),
    )
    area_campo = models.ForeignKey(
        AreaCampo, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="capas_mapa", verbose_name=_("Área del campo"),
    )
    variable = models.ForeignKey(
        VariableAnalitica, on_delete=models.CASCADE,
        related_name="capas", verbose_name=_("Variable"),
    )
    indice = models.ForeignKey(
        "IndiceVegetacion", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="capas", verbose_name=_("Índice de vegetación"),
    )
    medicion = models.ForeignKey(
        MedicionCampo, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="capas", verbose_name=_("Medición"),
    )
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_("Creada por"),
    )
    nombre = models.CharField(max_length=120, blank=True, verbose_name=_("Nombre"))
    fecha = models.DateField(verbose_name=_("Fecha"))
    visible = models.BooleanField(default=True, verbose_name=_("Visible"))
    datos = models.JSONField(null=True, blank=True, verbose_name=_("Datos GeoJSON"))
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Capa de mapa")
        verbose_name_plural = _("Capas de mapa")
        ordering = ["-fecha"]

    def __str__(self):
        return self.nombre or f"Capa {self.campo.nombre} {self.fecha}"


class EstiloCapa(models.Model):
    capa = models.OneToOneField(
        CapaMapa, on_delete=models.CASCADE,
        related_name="estilo", verbose_name=_("Capa"),
    )
    paleta = models.JSONField(
        default=list,
        help_text="Lista de colores hex ordenados de menor a mayor valor",
        verbose_name=_("Paleta de colores"),
    )
    opacidad = models.FloatField(default=0.7, verbose_name=_("Opacidad"))
    valor_minimo = models.FloatField(null=True, blank=True, verbose_name=_("Valor mínimo escala"))
    valor_maximo = models.FloatField(null=True, blank=True, verbose_name=_("Valor máximo escala"))

    class Meta:
        verbose_name = _("Estilo de capa")
        verbose_name_plural = _("Estilos de capa")

    def __str__(self):
        return f"Estilo — {self.capa}"
