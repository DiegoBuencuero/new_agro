from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from agro.models import Empresa
import re
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from agro.models import Empresa, Unidad, Moneda


class Campo(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE,verbose_name=_("Empresa"), )
    nombre = models.CharField( max_length=100, verbose_name=_("Nombre del campo"),)
    ciudad =models.ForeignKey("agro.Ciudad", on_delete=models.CASCADE, verbose_name=_("Ciudad / Localidad"), )
    descripcion = models.CharField( max_length=100, verbose_name=_("Descripción"), )
    superficie_ha = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Superficie total"),
        help_text=_("Superficie total del campo expresada en hectáreas"),
    )
    image = models.ImageField( default="default.jpg", upload_to="campos", verbose_name=_("Imagen"),)
    observaciones = models.TextField(null=True, blank=True, verbose_name=_("Observaciones"),)

    class Meta:
        verbose_name = _("Campo")
        verbose_name_plural = _("Campos")

    def __str__(self):
        return f"{self.nombre} ({self.superficie_ha} ha)"


class Lote(models.Model):
    class Meta:
        pass
    def __str__(self):
        return self.nombre

    campo = models.ForeignKey("Campo", verbose_name=("Campo"), on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    image = models.ImageField(default='default.jpg', upload_to='lotes')
    ha_totales = models.DecimalField(max_digits=6, decimal_places=2)
    ha_productivas = models.DecimalField(max_digits=6, decimal_places=2)

class Actividad(models.Model):
    class Meta:
        pass
    def __str__(self):
        return self.nombre
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=2)


class Cultivo(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name=_("Cultura"))

    class Meta:
        verbose_name = _("Cultura")
        verbose_name_plural = _("Culturas")
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Variedad(models.Model):
    cultivo = models.ForeignKey(Cultivo, on_delete=models.CASCADE, related_name="variedades", verbose_name=_("Cultura"))
    nombre = models.CharField(max_length=100, verbose_name=_("Variedade"))

    class Meta:
        verbose_name = _("Variedade")
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



class CicloAgricola(models.Model):
    def clean(self):
        if self.campo and self.campana:
            if self.campo.empresa != self.campana.empresa:
                raise ValidationError(
                    _("El campo y la campaña deben pertenecer a la misma empresa.")
                )
    def __str__(self):
        return f"{self.nombre_lote} – {self.campana} – {self.cultivo}"
    
    campo = models.ForeignKey(Campo, on_delete=models.CASCADE, related_name="ciclos")
    campana = models.ForeignKey(Campana, on_delete=models.CASCADE, related_name="ciclos")
    nombre_lote = models.CharField( max_length=50, blank= True, null=True )
    cultivo = models.ForeignKey( Cultivo, on_delete=models.CASCADE, related_name="ciclos")
    superficie_ha = models.DecimalField(max_digits=8, decimal_places=2)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    activa = models.BooleanField(default=True)


class FaseAgricola(models.Model):

    TIPO_FASE_CHOICES = [
        ('COB', 'Cobertura'),
        ('PRI', 'Cultivo principal'),
    ]
        
    ESTADO_FASE_CHOICES = [('abierto','Abierto'),('cerrado','Cerrado')]
    
    ciclo = models.ForeignKey(CicloAgricola, on_delete=models.CASCADE, related_name='fases')
    tipo = models.CharField(max_length=20, choices=TIPO_FASE_CHOICES, default='COB')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_FASE_CHOICES, default='abierto')

    class Meta:
        ordering = ['fecha_inicio']
        verbose_name = "Fase agrícola"
        verbose_name_plural = "Fases agrícolas"

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
    requiere_vist = models.BooleanField(default=False)
    requiere_cosecha = models.BooleanField(default=False)

class SubTipoActividad(models.Model):
    tipo_actividad = models.ForeignKey(TipoActividad, on_delete=models.CASCADE, related_name='subtipos')
    codigo = models.CharField(max_length=3)
    nombre = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tipo_actividad', 'codigo')

    def __str__(self):
        return f"{self.tipo_actividad.nombre} - {self.nombre}"

    
class ActividadProductiva(models.Model):
    fase = models.ForeignKey( FaseAgricola, on_delete=models.CASCADE, related_name='actividades')
    fecha = models.DateField()
    tipo = models.ForeignKey(TipoActividad, on_delete=models.CASCADE, related_name='actividades')
    subtipo = models.ForeignKey(SubTipoActividad,  on_delete=models.CASCADE, null=True, blank=True, related_name='actividades')
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
    
class CamposCosecha(models.Model):
    actividad = models.OneToOneField(ActividadProductiva, on_delete=models.CASCADE)
    rendimiento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Rendimiento obtenido (kg/ha, qq/ha, t/ha, según estándar)"),
    )
    comentarios_cosecha = models.TextField(
        null=True,
        blank=True,
        help_text=_("Observaciones específicas de la cosecha"),
    )
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text=_("Observaciones generales de la actividad"),
    )

class CategoriaProducto(models.Model):
    codigo = models.CharField(max_length=10, unique=True, verbose_name=_("Código"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre"))

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
    precio = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name=_("Precio"))
    maneja_stock = models.BooleanField(default=True, verbose_name=_("Maneja stock"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

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
    cultivo = models.ForeignKey(Cultivo, on_delete=models.PROTECT, related_name="productos_semilla", verbose_name=_("Cultivo"))
    variedad = models.ForeignKey(Variedad, on_delete=models.PROTECT, related_name="productos_semilla", verbose_name=_("Variedad"))

    class Meta:
        verbose_name = _("Producto semilla")
        verbose_name_plural = _("Productos semilla")

    def __str__(self):
        return f"{self.producto.nombre} - {self.cultivo} - {self.variedad}"

    def clean(self):
        if self.variedad and self.variedad.cultivo_id != self.cultivo_id:
            raise ValidationError({"variedad": _("La variedad no pertenece al cultivo seleccionado.")})

        if getattr(self.producto.categoria, "codigo", None) != "SEM":
            raise ValidationError({"producto": _("Solo los productos de categoría semilla pueden tener datos de semilla.")})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ActividadInsumo(models.Model):

    actividad = models.ForeignKey("ActividadProductiva", on_delete=models.CASCADE, related_name="insumos")
    producto = models.ForeignKey("gestion_agro.Producto", on_delete=models.CASCADE, null=True, blank=True)
    dosis = models.DecimalField(max_digits=10, decimal_places=2)
    um = models.ForeignKey(
        Unidad,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='actividad_insumos'
    )
    cantidad_real = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    costo_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    costo_ha = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)


class MovimientoStock(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", _("Entrada")
        SALIDA = "SALIDA", _("Salida")
   

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    um = models.ForeignKey(
        Unidad,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimientos_stock'
    )
    fecha = models.DateTimeField(default=timezone.now)
    actividad = models.ForeignKey(  
         "gestion_agro.ActividadProductiva",
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="movimientos_stock"
    )
    factura_item = models.ForeignKey("FacturaCompraItem", on_delete=models.CASCADE, null=True, blank=True)
    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        help_text=_("Precio promedio aplicado al momento del consumo"),
        null=True,
        blank=False,
    )

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

class ListaPrecio(models.Model):
    TIPO_CHOICES = [("CP", "Compra"), ("V", "Venta")]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="listas_precios")
    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES)
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT, related_name="listas_precios")
    unidad = models.ForeignKey(Unidad, on_delete=models.PROTECT, related_name="listas_precios")
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["empresa", "codigo"], name="uq_lista_precio_empresa_codigo")
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class ListaPrecioDetalle(models.Model):
    lista_precio = models.ForeignKey(ListaPrecio, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="precios")
    unidad = models.ForeignKey(Unidad, on_delete=models.PROTECT, related_name="precios_lista")
    precio = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lista_precio", "producto", "unidad"], name="uq_lista_precio_producto_unidad")
        ]

    def __str__(self):
        return f"{self.lista_precio} - {self.producto} - {self.precio}"







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
        
class ProductoExtractor:
    """Extrae y normaliza productos de facturas"""
    
    # Patrones para detectar envases y cantidades
    PATRONES_ENVASE = [
        (r'(\d+)\s*KG\s*BIG\s*BAG', 'big_bag', 'kg'),  # BIG BAG 750 KG
        (r'BIG\s*BAG\s*(\d+)\s*KG', 'big_bag', 'kg'),
        (r'(\d+)\s*L\s*BID[OÓ]N', 'bidon', 'L'),  # BIDÓN 20 L
        (r'BID[OÓ]N\s*(\d+)\s*L', 'bidon', 'L'),
        (r'(\d+)\s*L', 'liquido', 'L'),  # 5 L, 10 L
        (r'(\d+)\s*KG', 'suelto', 'kg'),  # 25 KG, 50 KG
        (r'(\d+)\s*GR', 'polvo', 'g'),  # 500 GR
        (r'(\d+)\s*G', 'polvo', 'g'),
        (r'(\d+,\d+)\s*KG', 'suelto', 'kg'),  # 0,5 KG
    ]
    
    # Unidades de conversión a estándar
    CONVERSIONES = {
        'kg': 1,
        'g': 0.001,
        'mg': 0.000001,
        'L': 1,
        'ml': 0.001,
        'und': None,  # Sin conversión
        'un': None,
        'cx': None,  # Caja
    }
    
    @staticmethod
    def extraer_detalle_factura(texto_factura):
        """Extrae productos del texto de factura"""
        
        productos = []
        
        # Buscar sección de productos (patrón NF-e brasileña)
        seccion_match = re.search(r'DADOS DO PRODUTO/SERVIÇOS(.*?)VALOR TOTAL DOS SERVIÇOS', 
                                 texto_factura, re.DOTALL | re.IGNORECASE)
        
        if seccion_match:
            seccion_texto = seccion_match.group(1)
            
            # Buscar líneas de productos - patrón NF-e
            lineas = re.finditer(
                r'(\d{6,10})\s+([A-Z][\w\s\-\./]+?)\s+(\d{8})\s+\d{3}\s+(\d{4})\s+(\w+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)',
                seccion_texto
            )
            
            for linea in lineas:
                producto = {
                    'codigo': linea.group(1).strip(),
                    'descripcion': linea.group(2).strip(),
                    'ncm': linea.group(3),
                    'cfop': linea.group(4),
                    'unidad_factura': linea.group(5).lower(),
                    'cantidad': Decimal(linea.group(6).replace('.', '').replace(',', '.')),
                    'precio_unitario': Decimal(linea.group(7).replace('.', '').replace(',', '.')),
                    'valor_total': Decimal(linea.group(8).replace('.', '').replace(',', '.')),
                }
                
                # Analizar envase y contenido
                producto.update(ProductoExtractor.analizar_envase(producto['descripcion']))
                
                productos.append(producto)
        
        # Si no encuentra con patrón NF-e, buscar genérico
        if not productos:
            productos = ProductoExtractor.buscar_patron_generico(texto_factura)
        
        return productos
    
    @staticmethod
    def analizar_envase(descripcion):
        """Analiza la descripción para extraer envase y contenido"""
        
        desc_upper = descripcion.upper()
        resultado = {
            'envase_tipo': 'desconocido',
            'envase_desc': '',
            'contenido_unidad': 'und',
            'contenido_cantidad': 1,
            'contenido_estandar': 1,
            'unidad_estandar': 'und'
        }
        
        # Buscar patrones de envase
        for patron, tipo, unidad in ProductoExtractor.PATRONES_ENVASE:
            match = re.search(patron, desc_upper, re.IGNORECASE)
            if match:
                cantidad = match.group(1).replace(',', '.')
                resultado.update({
                    'envase_tipo': tipo,
                    'envase_desc': f"{tipo} {cantidad}{unidad}",
                    'contenido_unidad': unidad,
                    'contenido_cantidad': Decimal(cantidad),
                    'unidad_estandar': unidad
                })
                break
        
        # Si no encuentra envase específico, buscar número seguido de unidad
        if resultado['envase_tipo'] == 'desconocido':
            match_generico = re.search(r'(\d+[\.,]?\d*)\s*(KG|L|GR|G|ML)\b', desc_upper)
            if match_generico:
                cantidad = match_generico.group(1).replace(',', '.')
                unidad = match_generico.group(2).lower()
                if unidad == 'gr':
                    unidad = 'g'
                
                resultado.update({
                    'envase_tipo': 'generico',
                    'envase_desc': f"{cantidad}{unidad}",
                    'contenido_unidad': unidad,
                    'contenido_cantidad': Decimal(cantidad),
                    'unidad_estandar': unidad
                })
        
        # Convertir a unidad estándar
        if resultado['unidad_estandar'] in ['kg', 'L']:
            resultado['contenido_estandar'] = resultado['contenido_cantidad']
        elif resultado['unidad_estandar'] == 'g':
            resultado['contenido_estandar'] = resultado['contenido_cantidad'] * 0.001
            resultado['unidad_estandar'] = 'kg'
        elif resultado['unidad_estandar'] == 'ml':
            resultado['contenido_estandar'] = resultado['contenido_cantidad'] * 0.001
            resultado['unidad_estandar'] = 'L'
        
        return resultado
    
    @staticmethod
    def buscar_patron_generico(texto):
        """Búsqueda genérica de productos en texto de factura"""
        
        productos = []
        
        # Buscar líneas con cantidades y precios
        patron = r'([A-Z][\w\s\-/]+?)\s+(\d+[\.,]?\d*)\s*([Kk]g|[Ll]|[Gg]r|[Mm]l|[Uu]nd)?\s+([\d\.,]+)\s+([\d\.,]+)'
        
        matches = re.finditer(patron, texto)
        
        for match in matches:
            producto = {
                'codigo': '',
                'descripcion': match.group(1).strip(),
                'unidad_factura': match.group(3).lower() if match.group(3) else 'und',
                'cantidad': Decimal(match.group(2).replace(',', '.')),
                'precio_unitario': Decimal(match.group(4).replace('.', '').replace(',', '.')),
                'valor_total': Decimal(match.group(5).replace('.', '').replace(',', '.'))
            }
            
            producto.update(ProductoExtractor.analizar_envase(producto['descripcion']))
            productos.append(producto)
        
        return productos


































# =========================
# PRESENTACIONES
# =========================

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




















# =========================
# PROVEEDORES
# =========================

class Proveedor_agro(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    razon_social = models.CharField(max_length=255, verbose_name=_("Razón social"))
    identificador = models.CharField(max_length=30, blank=True, null=True, verbose_name=_("CUIT / CNPJ"))

    class Meta:
        verbose_name = _("Proveedor")
        verbose_name_plural = _("Proveedores")
        unique_together = ("empresa", "razon_social")

    def __str__(self):
        return self.razon_social

# =========================
# FACTURAS DE COMPRA
# =========================

class FacturaCompra(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name=_("Empresa"))
    proveedor = models.ForeignKey(Proveedor_agro, on_delete=models.CASCADE, verbose_name=_("Proveedor"))
    numero = models.CharField(max_length=50, verbose_name=_("Número factura"))
    fecha = models.DateField(verbose_name=_("Fecha"))
    total = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Total"))
    archivo_pdf = models.FileField(upload_to="facturas_compra/", blank=True, null=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Factura de compra")
        verbose_name_plural = _("Facturas de compra")
        unique_together = ("empresa", "proveedor", "numero")

    def __str__(self):
        return f"{self.proveedor} - {self.numero}"

# =========================
# ÍTEMS DE FACTURA
# =========================

class FacturaCompraItem(models.Model):
    factura = models.ForeignKey(FacturaCompra, related_name="items", on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    presentacion = models.ForeignKey(PresentacionProducto, on_delete=models.CASCADE)
    cantidad_facturada = models.DecimalField(max_digits=12, decimal_places=3)
    cantidad_base = models.DecimalField(max_digits=14, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = _("Ítem de factura")
        verbose_name_plural = _("Ítems de factura")



