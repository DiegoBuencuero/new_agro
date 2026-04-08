from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db.models import Sum, F
from django.utils.translation import gettext_lazy as _
from django.db.models.functions import Coalesce


class Profile(models.Model):
    class Meta:
        pass
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    empresa = models.ForeignKey("Empresa", on_delete=models.CASCADE, null=True, blank=True)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics')
    tipo = models.CharField(max_length=1, default='A') 
    direccion = models.CharField(max_length=100, default='')
    direccion2 = models.CharField(max_length=100, default='')
    pais = models.ForeignKey("Pais", on_delete=models.CASCADE, null=True, blank=True)
    provincia = models.ForeignKey("Provincia", verbose_name=("Provincia"), on_delete=models.CASCADE, null=True, blank=True)
    ciudad = models.ForeignKey("Ciudad", verbose_name=("Ciudad"), on_delete=models.CASCADE, null=True, blank=True)
    cp = models.CharField(max_length=10, default='')
    telefono = models.CharField(max_length=30, default='', null=True, blank=True)
    celular = models.CharField(max_length=30, default='', null=True, blank=True)
    nacionalidad = models.ForeignKey("Nacionalidad", verbose_name=("Nacionalidad"), on_delete=models.CASCADE, null=True, blank=True)
    genero = models.ForeignKey("Genero", verbose_name=("Genero"), on_delete=models.CASCADE, null=True, blank=True)
    tipodoc = models.ForeignKey("Tipodoc", verbose_name=("Tipo documento"), on_delete=models.CASCADE, null=True, blank=True)
    documento = models.CharField(max_length=50, default='')
    fecha_nacimiento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=1, choices=[('N', 'Ingresado'), ('A', 'Aprobado'), ('S', 'Suspendido'), ], default='N')
    observaciones = models.CharField(null=True, blank=True, max_length=1000)
    add_date = models.DateTimeField(default=timezone.now)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class Moneda(models.Model):
    def __str__(self):
        return self.nombre
    nombre = models.CharField(max_length=50)
    corto = models.CharField(max_length=3)

class Cotizacion(models.Model):
    empresa = models.ForeignKey("Empresa", on_delete=models.CASCADE, null=True, blank=True)
    moneda = models.ForeignKey(Moneda, on_delete=models.CASCADE)
    fecha = models.DateTimeField()
    cotizacion = models.DecimalField(max_digits=12, decimal_places=3)

class Cotizacion_general(models.Model):
    moneda = models.ForeignKey(Moneda, on_delete=models.CASCADE)
    fecha = models.DateTimeField()
    cotizacion = models.DecimalField(max_digits=12, decimal_places=3)

class Tipodoc(models.Model):
    def __str__(self):
        return self.descripcion
    descripcion = models.CharField(max_length=50)

class Nacionalidad(models.Model):
    def __str__(self):
        return self.descripcion
    descripcion = models.CharField(max_length=50)
    pais = models.ForeignKey("Pais", verbose_name=("Pais"), on_delete=models.CASCADE)

class Genero(models.Model):
    def __str__(self):
        return self.descripcion
    descripcion = models.CharField(max_length=50)

class Pais(models.Model):
    def __str__(self):
        return self.nombre
    nombre = models.CharField(max_length=100)

class Provincia(models.Model):
    def __str__(self):
        return self.nombre
    nombre = models.CharField(max_length=100)
    pais = models.ForeignKey("Pais", verbose_name=("Pais"), on_delete=models.CASCADE)

class Ciudad(models.Model):
    nombre = models.CharField(max_length=100)
    provincia = models.ForeignKey(Provincia, verbose_name="Provincia", on_delete=models.CASCADE, related_name="ciudades")
    latitud = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True )

    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        unique_together = ("nombre", "provincia")

    def __str__(self):
        return f"{self.nombre} ({self.provincia})"

class Lista_de_precios(models.Model):
    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Lista de precios"
        verbose_name_plural = "Listas de precios"

class Empresa(models.Model):
    def __str__(self):
        return self.nombre
    class Meta:
        pass
    nombre = models.CharField(max_length=100)
    razon_social = models.CharField(max_length=100)
    cuit = models.CharField(max_length=50)
    status = models.CharField(max_length=1, choices=[('O', 'Ok'), ('B', 'Baja'), ('S', 'Suspendido'), ], default='O')
    add_date = models.DateTimeField(default=timezone.now)
    moneda = models.ForeignKey(Moneda, on_delete=models.CASCADE)
    unidad_default = models.ForeignKey("Unidad", on_delete=models.PROTECT, related_name="empresas", null=True, blank=True)
    lista_precio = models.ForeignKey(Lista_de_precios, on_delete=models.CASCADE, related_name="lista_de_precios", null=True, blank=True)
    valor_mobra = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name=_("Costo MO"))
    valor_maquina = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name=_("Costo Maquina"))

class Unidad(models.Model):
    nombre = models.CharField(max_length=50, verbose_name=_("Nombre"))
    abreviatura = models.CharField(max_length=10, verbose_name=_("Abreviatura"))
    factor_a_base = models.DecimalField(max_digits=10, decimal_places=6, verbose_name=_("Factor a unidad base"))

    class Meta:
        verbose_name = _("Unidad")
        verbose_name_plural = _("Unidades")

    def __str__(self):
        return self.abreviatura


class ConversionUM(models.Model):
    um_origen = models.ForeignKey(Unidad, on_delete=models.CASCADE, related_name="conversiones_origen")
    um_destino = models.ForeignKey(Unidad, on_delete=models.CASCADE, related_name="conversiones_destino")
    factor = models.DecimalField(max_digits=10, decimal_places=6, verbose_name=_("Factor de conversión"))

    class Meta:
        verbose_name = _("Conversión de unidad")
        verbose_name_plural = _("Conversiones de unidades")
        constraints = [
            models.UniqueConstraint(fields=["um_origen", "um_destino"], name="uq_conversion_um_origen_destino")
        ]

    def __str__(self):
        return f"{self.um_origen} → {self.um_destino} ({self.factor})"

    