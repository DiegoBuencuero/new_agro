from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class CapaAnalisis(models.Model):
    """
    Capa de análisis sobre un Campo.
    Ej: mapa de prescripción de KCl, análisis de pH, NDVI, rendimiento, etc.

    El shapefile se procesa UNA SOLA VEZ al subirlo y se guarda como
    GeoJSON minificado en disco. El navegador lo descarga directo
    (servido como archivo estático = súper rápido + cacheable).
    """

    TIPO_CHOICES = [
        ("prescripcion", _("Mapa de prescripción")),
        ("analisis_suelo", _("Análisis de suelo")),
        ("rendimiento", _("Mapa de rendimiento")),
        ("ndvi", _("NDVI / vegetación")),
        ("otro", _("Otro")),
    ]

    empresa = models.ForeignKey("agro.Empresa", on_delete=models.CASCADE, related_name="capas")
    campo = models.ForeignKey("gestion_agro.Campo", on_delete=models.CASCADE, related_name="capas")
    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="otro")

    # Variable y unidad. Ej: ("rate", "kg/ha"), ("ph", ""), ("k", "ppm")
    variable = models.CharField(
        max_length=50,
        help_text=_("Nombre del campo numérico en el shapefile (ej: rate, ph, k)"),
    )
    unidad = models.CharField(max_length=20, blank=True, default="")

    # GeoJSON pre-procesado (servido como archivo estático)
    geojson_file = models.FileField(upload_to="capas_geojson/")

    # Estadísticas pre-calculadas (para leyenda y escala de color)
    valor_min = models.FloatField(null=True, blank=True)
    valor_max = models.FloatField(null=True, blank=True)
    valor_promedio = models.FloatField(null=True, blank=True)
    num_features = models.IntegerField(default=0)

    # rectángulo delimitador pre-calculado (para centrar el mapa rápido)
    bbox_min_lng = models.FloatField(null=True, blank=True)
    bbox_min_lat = models.FloatField(null=True, blank=True)
    bbox_max_lng = models.FloatField(null=True, blank=True)
    bbox_max_lat = models.FloatField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-creado"]
        verbose_name = _("Capa de análisis")
        verbose_name_plural = _("Capas de análisis")

    def __str__(self):
        return self.nombre + " (" + self.campo.nombre + ")"

    @property
    def geojson_url(self):
        return self.geojson_file.url if self.geojson_file else ""


class NDVICaptura(models.Model):

    class Origen(models.TextChoices):
        AUTO   = "AUTO",   _("Sentinel-2 automático")
        MANUAL = "MANUAL", _("Subida manual")

    campo        = models.ForeignKey(
        "gestion_agro.Campo", on_delete=models.CASCADE,
        related_name="ndvi_capturas", verbose_name=_("Campo"),
    )
    ciclo        = models.ForeignKey(
        "gestion_agro.CicloAgricola", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="ndvi_capturas", verbose_name=_("Ciclo"),
    )
    fecha_imagen  = models.DateField(verbose_name=_("Fecha imagen satélite"))
    fecha_proceso = models.DateTimeField(default=timezone.now, verbose_name=_("Fecha proceso"))
    origen        = models.CharField(max_length=10, choices=Origen.choices, default=Origen.AUTO)

    ndvi_promedio = models.FloatField(null=True, blank=True, verbose_name=_("NDVI promedio"))
    ndvi_min      = models.FloatField(null=True, blank=True, verbose_name=_("NDVI mínimo"))
    ndvi_max      = models.FloatField(null=True, blank=True, verbose_name=_("NDVI máximo"))
    nubosidad_pct = models.FloatField(default=0, verbose_name=_("% Nubosidad"))

    imagen_png    = models.ImageField(upload_to="ndvi/imagenes/", null=True, blank=True, verbose_name=_("Imagen PNG"))
    geojson_file  = models.FileField(upload_to="ndvi/geojson/", null=True, blank=True, verbose_name=_("GeoJSON"))

    class Meta:
        ordering = ["-fecha_imagen"]
        unique_together = ("campo", "fecha_imagen")
        verbose_name = _("Captura NDVI")
        verbose_name_plural = _("Capturas NDVI")

    def __str__(self):
        return f"{self.campo.nombre} – {self.fecha_imagen} – NDVI {self.ndvi_promedio:.3f}" if self.ndvi_promedio else f"{self.campo.nombre} – {self.fecha_imagen}"

    @property
    def estado(self):
        if self.ndvi_promedio is None:
            return "sin_datos"
        if self.ndvi_promedio >= 0.5:
            return "optimo"
        if self.ndvi_promedio >= 0.3:
            return "normal"
        if self.ndvi_promedio >= 0.1:
            return "estres"
        return "critico"
