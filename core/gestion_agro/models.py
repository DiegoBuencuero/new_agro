from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from agro.models import Empresa, Unidad

DESTINO_CHOICES = [
    ("M", _("Semilla (Multiplicación)")),
    ("C", _("Consumo")),
]


class Campo(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE,verbose_name=_("Empresa"), )
    nombre = models.CharField( max_length=100, verbose_name=_("Nombre del campo"),)
    ciudad =models.ForeignKey("agro.Ciudad", on_delete=models.CASCADE, verbose_name=_("Ciudad / Localidad"), )
    descripcion = models.CharField( max_length=100, verbose_name=_("Descripción"), )
    superficie_ha = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Superficie productiva (ha)"),
        help_text=_("Superficie productiva del campo expresada en hectáreas"),
    )
    image = models.ImageField( default="default.jpg", upload_to="campos", verbose_name=_("Imagen"),)
    observaciones = models.TextField(null=True, blank=True, verbose_name=_("Observaciones"),)
    contorno      = models.TextField(null=True, blank=True, verbose_name=_("Contorno (GeoJSON)"))
    ## CONTORNO LO TENDRIAMOS QUE PASAR POR EFICIENCIA A GEOMETRYFIELD, cuando psames  a postgres

    class Meta:
        verbose_name = _("Campo")
        verbose_name_plural = _("Campos")

    def __str__(self):
        return f"{self.nombre} ({self.superficie_ha} ha)"

    @property
    def areas_geojson_union(self):
        """GeoJSON FeatureCollection con todas las áreas del campo."""
        features = []
        for area in self.areas.all():
            if area.contorno:
                import json
                try:
                    geom = json.loads(area.contorno)
                    features.append({
                        "type": "Feature",
                        "properties": {"id": area.id, "nombre": area.nombre},
                        "geometry": geom if geom.get("type") != "FeatureCollection" else geom["features"][0]["geometry"],
                    })
                except Exception:
                    pass
        return {"type": "FeatureCollection", "features": features}

class AreaCampo(models.Model):
    campo         = models.ForeignKey(Campo, on_delete=models.CASCADE, related_name="areas", verbose_name=_("Campo"))
    ciclo         = models.ForeignKey(
        "CicloAgricola", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="areas", verbose_name=_("Ciclo agrícola"),
    )
    nombre        = models.CharField(max_length=100, verbose_name=_("Nombre del área"))
    contorno      = models.TextField(null=True, blank=True, verbose_name=_("Contorno (GeoJSON)"))
    superficie_ha = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, verbose_name=_("Superficie (ha)"))
    descripcion   = models.CharField(max_length=255, blank=True, verbose_name=_("Descripción"))
    creado        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("Área del campo")
        verbose_name_plural = _("Áreas del campo")
        ordering            = ["nombre"]

    def __str__(self):
        return f"{self.campo.nombre} — {self.nombre}"

class Lote(models.Model):
    campo = models.ForeignKey("Campo", verbose_name=_("Campo"), on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    image = models.ImageField(default='default.jpg', upload_to='lotes')
    ha_totales = models.DecimalField(max_digits=6, decimal_places=2)
    ha_productivas = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return self.nombre

class Actividad(models.Model):
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=2)

    def __str__(self):
        return self.nombre

class Cultivo(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="cultivos")
    nombre = models.CharField(max_length=100, unique=True, verbose_name=_("Cultura"))
    producto_default = models.ForeignKey(
        "Producto",
        on_delete=models.CASCADE,
        related_name="cultivos",
        verbose_name=_("Producto asociado"),
        null=True,
        blank=True
    )
    productos_finales = models.ManyToManyField(
        "Producto",
        related_name="cultivos_finales",
        blank=True,
        verbose_name=_("Productos finales (cosecha)")
    )

    class Meta:
        verbose_name = _("Cultura")
        verbose_name_plural = _("Culturas")
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

class Variedad(models.Model):
    cultivo = models.ForeignKey(Cultivo, on_delete=models.CASCADE, related_name="variedades", verbose_name=_("Cultura"))
    nombre  = models.CharField(max_length=100, verbose_name=_("Variedad"))
    pmg     = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        verbose_name=_("PMG (g)"),
        help_text=_("Peso de mil granos en gramos"),
    )

    class Meta:
        verbose_name = _("Variedad")
        verbose_name_plural = _("Variedades")
        ordering = ["cultivo__nombre", "nombre"]
        unique_together = ("cultivo", "nombre")

    def __str__(self):
        return f"{self.cultivo} - {self.nombre}"

class Campana(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    nombre = models.CharField(max_length=9, editable=False, verbose_name=_("Campaña"))   
    fecha_desde = models.DateField(verbose_name=_("Fecha de inicio"))
    fecha_hasta = models.DateField(verbose_name=_("Fecha de finalización"))
    activa = models.BooleanField(default=False, verbose_name=_("Campaña activa"))
    observaciones = models.TextField(null=True, blank=True, verbose_name=_("Observaciones"))

    class Meta:
        verbose_name = _("Campaña")
        verbose_name_plural = _("Campañas")
        ordering = ["-fecha_desde"]
        unique_together = ("empresa", "nombre")

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.fecha_hasta < self.fecha_desde:
            raise ValidationError(_("La fecha de finalización debe ser mayor a la fecha de inicio"))

    def save(self, *args, **kwargs):
        if self.fecha_desde:
            anio = self.fecha_desde.year
            self.nombre = f"{anio}/{anio + 1}"
        if self.activa:
            Campana.objects.filter(empresa=self.empresa, activa=True).exclude(id=self.id).update(activa=False)
        super().save(*args, **kwargs)

class Deposito(models.Model):

    class TipoDeposito(models.TextChoices):
        PROPIO = "PROPIO", "Propio"
        EXTERNO = "EXTERNO", "Externo"

    empresa     = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nombre      = models.CharField(max_length=100)
    tipo        = models.CharField(max_length=10, choices=TipoDeposito.choices, default=TipoDeposito.PROPIO)

    ciudad      = models.ForeignKey("agro.Ciudad", on_delete=models.CASCADE)
    direccion   = models.CharField(max_length=100, blank=True)
    telefono    = models.CharField(max_length=30, blank=True)
    descripcion = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"

class CicloAgricola(models.Model):
    campo         = models.ForeignKey(Campo, on_delete=models.CASCADE, related_name="ciclos")
    area          = models.ForeignKey(AreaCampo, on_delete=models.PROTECT, null=True, blank=True, related_name="ciclos")
    campana       = models.ForeignKey(Campana, on_delete=models.CASCADE, related_name="ciclos")
    nombre_lote   = models.CharField(max_length=50, blank=True, null=True)
    cultivo       = models.ForeignKey(Cultivo, on_delete=models.CASCADE, related_name="ciclos")
    producto_final = models.ForeignKey(
        "Producto", on_delete=models.CASCADE,
        null=True, blank=True, related_name="ciclos_producto_final",
    )
    contorno      = models.TextField(null=True, blank=True, verbose_name=_("Contorno del lote (GeoJSON)"))
    superficie_ha = models.DecimalField(max_digits=8, decimal_places=2)
    fecha_inicio  = models.DateField()
    fecha_fin     = models.DateField(null=True, blank=True)
    activa        = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Ciclo agrícola")
        verbose_name_plural = _("Ciclos agrícolas")
        ordering = ["-fecha_inicio", "-id"]

    def clean(self):
        errores = {}

        if self.campo_id and self.campana_id:
            if self.campo.empresa_id != self.campana.empresa_id:
                errores["campana"] = _("El campo y la campaña deben pertenecer a la misma empresa.")

        if self.cultivo_id and self.campo_id:
            if self.cultivo.empresa_id != self.campo.empresa_id:
                errores["cultivo"] = _("El cultivo y el campo deben pertenecer a la misma empresa.")

        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_fin < self.fecha_inicio:
                errores["fecha_fin"] = _("La fecha de fin no puede ser anterior a la fecha de inicio.")

        if self.cultivo_id:
            producto_default = self.cultivo.producto_default
            if not producto_default:
                errores["cultivo"] = _("El cultivo seleccionado no tiene un producto final por defecto.")
            elif self.producto_final_id and self.producto_final_id != producto_default.id:
                if not self.cultivo.productos_finales.filter(id=self.producto_final_id).exists():
                    errores["producto_final"] = _("El producto final no corresponde al cultivo seleccionado.")

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.cultivo and not self.producto_final_id and self.cultivo.producto_default:
            self.producto_final = self.cultivo.producto_default
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_lote} – {self.campana} – {self.cultivo}"

class FaseAgricola(models.Model):
    TIPO_FASE_CHOICES = [
        ('COB', _('Cobertura')),
        ('PRI', _('Cultivo principal')),
    ]

    ESTADO_FASE_CHOICES = [('abierto', _('Abierto')), ('cerrado', _('Cerrado'))]

    ciclo = models.ForeignKey(CicloAgricola, on_delete=models.CASCADE, related_name='fases')
    tipo = models.CharField(max_length=20, choices=TIPO_FASE_CHOICES, default='COB')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_FASE_CHOICES, default='abierto')

    class Meta:
        ordering = ['fecha_inicio']
        verbose_name = _("Fase agrícola")
        verbose_name_plural = _("Fases agrícolas")

    def __str__(self):
        return f"{self.ciclo} - {self.get_tipo_display()} ({self.estado})"

    def duracion_dias(self):
        if self.fecha_fin:
            return (self.fecha_fin - self.fecha_inicio).days + 1
        return None

    def es_activa(self):
        return self.estado == 'abierto'
    
class TipoActividad(models.Model):
    def __str__(self):
        return f"{self.nombre} ({self.tipo})"
    nombre = models.CharField(max_length=30)
    tipo = models.CharField(max_length=1)
    activo = models.BooleanField(default=True)
    abre_fase = models.BooleanField(default=False)
    cierra_fase = models.BooleanField(default=False)
    requiere_subtipo = models.BooleanField(default=False)
    adicionales = models.BooleanField(default=False)
    requiere_insumo = models.BooleanField(default=False)
    requiere_mo = models.BooleanField(default=False)
    requiere_maq = models.BooleanField(default=False)
    requiere_vist       = models.BooleanField(default=False)
    requiere_cosecha    = models.BooleanField(default=False)
    requiere_inspeccion = models.BooleanField(default=False, verbose_name=_("Requiere inspección semilla"))
    valor_x_ha_mo = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Horas de mano de obra por ha"))
    valor_x_ha_mq = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Horas de máquina por ha"))
    valor_mo = models.DecimalField(max_digits=18, decimal_places=4, default=0, null=True, blank=True, verbose_name=_("Costo por hora de mano de obra"))
    valor_maquina = models.DecimalField(max_digits=18, decimal_places=2, default=0, null=True, blank=True, verbose_name=_("Costo por hora de máquina"))

class SubTipoActividad(models.Model):
    tipo_actividad = models.ForeignKey(TipoActividad, on_delete=models.CASCADE, related_name='subtipos')
    codigo = models.CharField(max_length=3)
    nombre = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    activo = models.BooleanField(default=True)
    abre_fase = models.BooleanField(null=True, blank=True )
    cierra_fase = models.BooleanField(null=True, blank=True )
    valor_x_ha_mo = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Horas de mano de obra por ha"))
    valor_x_ha_mq = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Horas de máquina por ha"))
    valor_mo = models.DecimalField(max_digits=18, decimal_places=4, default=0, null=True, blank=True, verbose_name=_("Costo por hora de mano de obra"))
    valor_maquina = models.DecimalField(max_digits=18, decimal_places=2, default=0, null=True, blank=True, verbose_name=_("Costo por hora de máquina"))

    class Meta:
        unique_together = ('tipo_actividad', 'codigo')

    def __str__(self):
        return f"{self.tipo_actividad.nombre} - {self.nombre}"
    
class ActividadProductiva(models.Model):
    fase = models.ForeignKey( FaseAgricola, on_delete=models.CASCADE, related_name='actividades')
    fecha = models.DateField()
    tipo = models.ForeignKey(TipoActividad, on_delete=models.CASCADE, related_name='actividades')
    subtipo = models.ForeignKey(SubTipoActividad,  on_delete=models.CASCADE, null=True, blank=True, related_name='actividades')
    cantidad_hombre = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    valor_hombre = models.DecimalField(max_digits=18, decimal_places=2, default=0, null=True, blank=True)
    cantidad_h_maq = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    valor_h_maq = models.DecimalField(max_digits=18, decimal_places=2, default=0, null=True, blank=True)

    total_mo  = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    total_maq = models.DecimalField(max_digits=8,decimal_places=2, null=True, blank=True)
    total     = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.tipo.nombre} - {self.fecha}"

class CamposVistoria(models.Model):
    actividad = models.OneToOneField(ActividadProductiva, on_delete=models.CASCADE)
    plantas_m2 = models.IntegerField(null=True, blank=True)
    malezas = models.CharField(max_length=255, blank=True, null=True)
    insectos = models.CharField(max_length=255, blank=True, null=True)
    enfermedades = models.CharField(max_length=255, blank=True, null=True)
    imagen = models.ImageField(upload_to='vistorias/', null=True, blank=True)

    def __str__(self):
        return f"Vistoria · {self.actividad.fecha.strftime('%d/%m/%Y')}"
    
class CamposInspeccion(models.Model):
    class Resultado(models.TextChoices):
        APROBADO  = 'APROBADO',  _('Aprobado')
        RECHAZADO = 'RECHAZADO', _('Rechazado')

    actividad          = models.OneToOneField(ActividadProductiva, on_delete=models.CASCADE)
    cant_semilla_mult_ha = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name=_("Cantidad aprobada (por ha)"))
    um                 = models.ForeignKey('agro.Unidad', on_delete=models.CASCADE, related_name='inspeccion_unidad_medida', verbose_name=_("Unidad"))
    resultado          = models.CharField(max_length=10, choices=Resultado.choices, null=True, blank=True, verbose_name=_("Resultado"))
    responsable        = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Responsable"))

    class Meta:
        verbose_name        = _("Inspección de semilla")
        verbose_name_plural = _("Inspecciones de semilla")

    def __str__(self):
        return f"Inspección · {self.actividad.fecha.strftime('%d/%m/%Y')} · {self.get_resultado_display() or '—'}"
        
class CamposCosecha(models.Model):
    actividad = models.OneToOneField(ActividadProductiva, on_delete=models.CASCADE)
    rendimiento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Rendimiento (por ha)"),
        help_text=_("Rendimiento obtenido (kg/ha, qq/ha, t/ha, según estándar)"),
    )
    comentarios_cosecha = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Comentarios de cosecha"),
    )
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Observaciones"),
    )

    class Meta:
        verbose_name        = _("Cosecha")
        verbose_name_plural = _("Cosechas")

class CategoriaProducto(models.Model):
    codigo = models.CharField(max_length=10, unique=True, verbose_name=_("Código"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre"))
    es_semilla = models.BooleanField(default=False, verbose_name=_("Es semilla"))

    class Meta:
        verbose_name = _("Categoría de producto")
        verbose_name_plural = _("Categorías de producto")

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="productos")
    codigo = models.CharField(max_length=50, verbose_name=_("Código"))
    nombre = models.CharField(max_length=255, verbose_name=_("Nombre"))
    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.PROTECT, related_name="productos", verbose_name=_("Categoría"))
    unidad_base = models.ForeignKey(Unidad, on_delete=models.PROTECT, related_name="productos_unidad_base", verbose_name=_("Unidad base"))
    presentacion_defualt = models.ForeignKey("PresentacionProducto", on_delete=models.SET_NULL, null=True, blank=True, related_name="productos_presentacion_default", verbose_name=_("Presentación default"))
    precio = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name=_("Precio"))
    maneja_stock = models.BooleanField(default=True, verbose_name=_("Maneja stock"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))
    producto_final = models.BooleanField(default=False, verbose_name=_("Producto final (cosecha)"))
    deposito_default = models.ForeignKey('Deposito', on_delete=models.SET_NULL, null=True, blank=True, related_name="productos_default")

    class Meta:
        verbose_name = _("Producto")
        verbose_name_plural = _("Productos")
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "codigo"], name="uq_producto_empresa_codigo")
        ]

    def __str__(self):
        return self.nombre

class ProductoSemilla(models.Model):
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE, related_name="datos_semilla", verbose_name=_("Producto"))
    cultivo  = models.ForeignKey(Cultivo, on_delete=models.PROTECT, related_name="productos_semilla", verbose_name=_("Cultivo"))
    variedad = models.ForeignKey(Variedad, on_delete=models.PROTECT, related_name="productos_semilla", verbose_name=_("Variedad"))

    class Meta:
        verbose_name = _("Producto semilla")
        verbose_name_plural = _("Productos semilla")

    def __str__(self):
        return f"{self.producto.nombre} - {self.cultivo} - {self.variedad}"

    def clean(self):
        if self.variedad and self.variedad.cultivo_id != self.cultivo_id:
            raise ValidationError({
                "variedad": _("La variedad no pertenece al cultivo seleccionado.")
            })

        if not self.producto_id or not self.producto.categoria_id:
            return

        if not self.producto.categoria.es_semilla:
            raise ValidationError({
                "producto": _("Solo los productos de categoría semilla pueden tener datos de semilla.")
            })
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class ActividadInsumo(models.Model):

    actividad       = models.ForeignKey("ActividadProductiva", on_delete=models.CASCADE, related_name="insumos")
    producto        = models.ForeignKey("gestion_agro.Producto", on_delete=models.CASCADE, null=True, blank=True)
    dosis           = models.DecimalField(max_digits=10, decimal_places=2)
    um              = models.ForeignKey(Unidad, on_delete=models.CASCADE, null=True, blank=True, related_name='actividad_insumos')
    densidad_siembra = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name=_("Densidad de siembra (semillas/ha)"))
    cantidad_real   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    costo_total     = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    costo_ha        = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

class MovimientoStock(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", _("Entrada")
        SALIDA  = "SALIDA",  _("Salida")
        VENTA   = "VENTA",   _("Venta")

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    um = models.ForeignKey( Unidad, on_delete=models.CASCADE,  null=True, blank=True, related_name='movimientos_stock' )
    fecha = models.DateTimeField(default=timezone.now)
    actividad_item = models.ForeignKey(   "gestion_agro.ActividadInsumo",  on_delete=models.CASCADE,  null=True,  blank=True, related_name="movimientos_stock" )
    actividad = models.ForeignKey( "ActividadProductiva",  on_delete=models.CASCADE,   blank=True,  null=True,  related_name="movimientos_stock" )    
    factura_item       = models.ForeignKey("FacturaCompraItem", on_delete=models.CASCADE, null=True, blank=True)
    factura_venta_item = models.ForeignKey("administracion.FacturaVentaItem", on_delete=models.SET_NULL, null=True, blank=True, related_name="movimientos_stock", verbose_name=_("Ítem venta"))
    cosecha = models.ForeignKey("CamposCosecha", on_delete=models.SET_NULL, null=True, blank=True, related_name="movimientos_stock", verbose_name=_("Cosecha"))
    destino = models.CharField(max_length=1, blank=True, null=True, choices=DESTINO_CHOICES, verbose_name=_("Destino"))
    es_semilla_cosecha = models.BooleanField(default=False, verbose_name=_("Es porción semilla de cosecha"))
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=6, help_text=_("Precio promedio aplicado al momento del consumo"), null=True, blank=False)
    deposito_origen  = models.ForeignKey(Deposito, on_delete=models.CASCADE, null=True, blank=True, related_name="salidas")
    deposito_destino = models.ForeignKey(Deposito, on_delete=models.CASCADE, null=True, blank=True, related_name="entradas")
    class Meta:
        verbose_name = _("Movimiento de stock")
        verbose_name_plural = _("Movimientos de stock")

class TipoActividadCategoriaProducto(models.Model):
    tipo_actividad = models.ForeignKey(TipoActividad, on_delete=models.CASCADE, related_name="categorias_producto")
    subtipo_actividad = models.ForeignKey(SubTipoActividad, on_delete=models.CASCADE, null=True, blank=True, related_name="categorias_producto")
    categoria_producto = models.ForeignKey(CategoriaProducto, on_delete=models.CASCADE, related_name="tipos_actividad")
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ("tipo_actividad", "subtipo_actividad", "categoria_producto")

    def __str__(self):
        if self.subtipo_actividad:
            return f"{self.tipo_actividad} / {self.subtipo_actividad} → {self.categoria_producto}"
        return f"{self.tipo_actividad} → {self.categoria_producto}"

class FacturaCompra(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    proveedor = models.ForeignKey("Proveedor", on_delete=models.CASCADE, verbose_name=_("Proveedor"))
    numero = models.CharField(max_length=50, verbose_name=_("Número factura"))
    fecha = models.DateField(verbose_name=_("Fecha"))
    total = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Total"))
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name=_("Fecha vencimiento"))
    archivo_pdf = models.FileField(upload_to="facturas_compra/", blank=True, null=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Factura de compra")
        verbose_name_plural = _("Facturas de compra")
        unique_together = ("empresa", "proveedor", "numero")

    def __str__(self):  
        return f"{self.proveedor} - {self.numero}"

class FacturaCompraItem(models.Model):
    factura = models.ForeignKey(FacturaCompra, related_name="items", on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    presentacion = models.ForeignKey("PresentacionProducto", on_delete=models.CASCADE)
    cantidad_facturada = models.DecimalField(max_digits=12, decimal_places=3)
    cantidad_base = models.DecimalField(max_digits=14, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = _("Ítem de factura")
        verbose_name_plural = _("Ítems de factura")

class PresentacionProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, verbose_name=_("Producto"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre presentación"))
    unidad_factura = models.CharField(max_length=20, verbose_name=_("Unidad factura"))
    contenido = models.DecimalField(max_digits=12, decimal_places=3, verbose_name=_("Contenido"))
    unidad_contenido = models.ForeignKey("agro.Unidad", on_delete=models.CASCADE, verbose_name=_("Unidad contenido"))

    class Meta:
        verbose_name = _("Presentación de producto")
        verbose_name_plural = _("Presentaciones de producto")

    def __str__(self):
        return f"{self.producto} - {self.nombre}"

class Proveedor(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    razon_social = models.CharField(max_length=255, verbose_name=_("Razón social"))
    identificador = models.CharField(max_length=30, blank=True, null=True, verbose_name=_("CUIT / CNPJ"))

    class Meta:
        verbose_name = _("Proveedor")
        verbose_name_plural = _("Proveedores")
        unique_together = ("empresa", "razon_social")

    def __str__(self):
        return self.razon_social

class Cliente(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    razon_social = models.CharField(max_length=255, verbose_name=_("Razón social"))
    identificador = models.CharField(max_length=30, blank=True, null=True, verbose_name=_("CUIT / CNPJ"))

    class Meta:
        verbose_name = _("Cliente")
        verbose_name_plural = _("Clientes")
        unique_together = ("empresa", "razon_social")

    def __str__(self):
        return self.razon_social

class ProductoNormalizado(models.Model):
    """Productos extraídos y normalizados de facturas"""
    
    UNIDADES_ESTANDAR = [
        ('kg', 'Kilogramos'),
        ('L', 'Litros'),
        ('g', 'Gramos'),
        ('ml', 'Mililitros'),
        ('ha', 'Hectárea'),
        ('und', 'Unidad'),
    ]
    
    # Datos de origen
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    origen_descripcion = models.TextField(verbose_name=_("Descripción original"))
    origen_codigo = models.CharField(max_length=50, blank=True, verbose_name=_("Código original"))
    
    # Datos normalizados
    nombre = models.CharField(max_length=200, verbose_name=_("Nombre del producto"))
    envase_tipo = models.CharField(max_length=50, verbose_name=_("Tipo de envase"))
    envase_desc = models.CharField(max_length=100, verbose_name=_("Descripción envase"))
    
    # Contenido
    contenido_cantidad = models.DecimalField(max_digits=10, decimal_places=3, verbose_name=_("Cantidad por envase"))
    contenido_unidad = models.CharField(max_length=10, verbose_name=_("Unidad contenido"))
    contenido_estandar = models.DecimalField(max_digits=12, decimal_places=4, verbose_name=_("Cantidad estándar"))
    unidad_estandar = models.CharField(max_length=10, choices=UNIDADES_ESTANDAR, verbose_name=_("Unidad estándar"))
    
    # Para cálculo por hectárea
    dosis_recomendada = models.DecimalField(max_digits=10, decimal_places=4, default=0, 
                                           verbose_name=_("Dosis (por ha)"))
    dosis_unidad = models.CharField(max_length=10, choices=UNIDADES_ESTANDAR, default='L',
                                   verbose_name=_("Unidad dosis"))
    
    # Costos
    precio_envase = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Precio por envase"))
    costo_por_unidad = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                          verbose_name=_("Costo por unidad estándar"))
    costo_por_ha = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                      verbose_name=_("Costo por hectárea"))
    
    fecha_importacion = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha importación"))
    
    class Meta:
        verbose_name = _("Producto normalizado")
        verbose_name_plural = _("Productos normalizados")
        ordering = ['-fecha_importacion']
    
    def calcular_costos(self):
        """Calcula costos por unidad y por hectárea"""
        if self.contenido_estandar > 0:
            # Costo por unidad estándar (ej: por kg o por L)
            self.costo_por_unidad = self.precio_envase / self.contenido_estandar
        
        if self.dosis_recomendada > 0:
            # Costo por hectárea
            self.costo_por_ha = self.costo_por_unidad * self.dosis_recomendada
        
        # Guardar los cambios
        self.save(update_fields=['costo_por_unidad', 'costo_por_ha'])
    
    def __str__(self):
        return f"{self.nombre} - {self.envase_desc}"
