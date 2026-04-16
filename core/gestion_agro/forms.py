from django import forms
from django.utils.translation import gettext as _
from django.forms import inlineformset_factory, formset_factory, BaseFormSet, BaseInlineFormSet
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User  
from django.utils import timezone
from django.forms import ModelForm
from agro.models import Ciudad, Unidad
from gestion_agro.models import (Campo, Campana, CicloAgricola, Cultivo, ActividadProductiva, TipoActividad, SubTipoActividad,
                                ActividadInsumo, CamposVistoria, CamposCosecha, Producto, CategoriaProducto, FacturaCompra,
                                Proveedor, FacturaCompraItem, PresentacionProducto, Variedad, MovimientoStock)
from django.db.models import Q, Sum


from django.utils.translation import gettext_lazy as _
from gestion_agro.models import (
    CategoriaProducto, Cultivo, Variedad, Producto, PresentacionProducto
)
from agro.models import Unidad


class BaseForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(BaseForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class BaseSimpleForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(BaseSimpleForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class CampoForm(BaseForm):
    class Meta:
        model = Campo
        fields = ["nombre", "ciudad", "superficie_ha", "descripcion", "image", "observaciones"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 2}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

class CampanaForm(BaseForm):
    class Meta:
        model = Campana
        exclude = ["empresa", "nombre"]
        widgets = {
            "fecha_desde": forms.DateInput(attrs={"type": "date"}),
            "fecha_hasta": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

class CicloForm(BaseForm):
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
           self.fields["fecha_inicio"].initial = timezone.localdate()

        if empresa:
            self.fields["campo"].queryset = Campo.objects.filter(empresa=empresa).order_by("nombre")
            self.fields["campana"].queryset = Campana.objects.filter(empresa=empresa).order_by("-fecha_desde")

            campana_activa = Campana.objects.filter(
                empresa=empresa,
                activa=True
            ).first()

            if campana_activa:
                self.fields["campana"].initial = campana_activa

    class Meta:
        model = CicloAgricola
        fields = ["campo", "campana", "cultivo", "superficie_ha", "fecha_inicio", "fecha_fin"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

class CicloFiltroForm(BaseSimpleForm):
    campana = forms.ModelChoiceField(queryset=None, required=False, empty_label="Todas", label="Campaña")
    campo = forms.ModelChoiceField(queryset=None, required=False, empty_label="Todos", label="Campo" )
    cultivo = forms.ModelChoiceField(queryset=None, required=False, empty_label="Todos", label="Cultivo")
    estado = forms.ChoiceField(choices=[("", "Todos"), ("activo", "Activo"), ("cerrado", "Cerrado"), ], required=False, label="Estado" )

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)

        if empresa:
            self.fields["campana"].queryset = Campana.objects.filter(empresa=empresa).order_by("-fecha_desde")
            self.fields["campo"].queryset = Campo.objects.filter(empresa=empresa).order_by("nombre")

        self.fields["cultivo"].queryset = Cultivo.objects.all().order_by("nombre")

class ActividadProductivaForm(BaseForm):
    class Meta:
        model = ActividadProductiva
        fields = (
            "fecha",
            "tipo",
            "subtipo",
            "cantidad_hombre",
            "valor_hombre",
            "cantidad_h_maq",
            "valor_h_maq",
            "observaciones",
        )
        widgets = {
            "fecha": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "cantidad_hombre": forms.NumberInput(attrs={
                "step": "0.01",
                "placeholder": _("Horas de mano de obra"),
            }),
            "valor_hombre": forms.NumberInput(attrs={
                "step": "0.01",
                "placeholder": _("Costo por hora"),
            }),
            "cantidad_h_maq": forms.NumberInput(attrs={
                "step": "0.01",
                "placeholder": _("Horas de máquina"),
            }),
            "valor_h_maq": forms.NumberInput(attrs={
                "step": "0.01",
                "placeholder": _("Costo por hora"),
            }),
            "observaciones": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": _("Observaciones"),
            }),
        }

        labels = {
            "cantidad_hombre": _("Horas de mano de obra"),
            "valor_hombre": _("Costo por hora"),
            "cantidad_h_maq": _("Horas de máquina"),
            "valor_h_maq": _("Costo por hora"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound and not self.instance.pk:
            self.initial["fecha"] = timezone.localdate()

        self.fields["tipo"].queryset = TipoActividad.objects.filter(activo=True)
        self.fields["subtipo"].required = False

        if self.is_bound:
            tipo_id = self.data.get("tipo")
        elif self.instance.pk:
            tipo_id = self.instance.tipo_id
        else:
            tipo_id = None

        if tipo_id:
            self.fields["subtipo"].queryset = SubTipoActividad.objects.filter(
                tipo_actividad_id=tipo_id,
                activo=True,
            )
        else:
            self.fields["subtipo"].queryset = SubTipoActividad.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")
        subtipo = cleaned_data.get("subtipo")

        if tipo and subtipo and subtipo.tipo_actividad_id != tipo.id:
            self.add_error("subtipo", _("El subtipo no corresponde al tipo seleccionado."))

        return cleaned_data

class ActividadInsumoForm(BaseForm):
    class Meta:
        model = ActividadInsumo
        fields = ["producto", "dosis", "um"]
        widgets = {
            "producto": forms.Select(),
            "dosis": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "um": forms.Select(),
        }
        labels = {
            "producto": _("Producto"),
            "dosis": _("Dosis"),
            "um": _("Unidad"),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)

        self.fields["producto"].required = False
        self.fields["dosis"].required = False
        self.fields["um"].required = False

        self.fields["producto"].queryset = Producto.objects.none()
        self.fields["um"].queryset = Unidad.objects.all().order_by("nombre")

        if empresa:
            self.fields["producto"].queryset = (
                Producto.objects
                .filter(empresa=empresa, activo=True, maneja_stock=True)
                .select_related("unidad_base", "categoria")
                .order_by("nombre")
            )

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("DELETE"):
            return cleaned_data

        producto = cleaned_data.get("producto")
        dosis = cleaned_data.get("dosis")
        um = cleaned_data.get("um")

        if not any([producto, dosis, um]):
            return cleaned_data

        if not producto:
            self.add_error("producto", _("Debe seleccionar un producto."))
        if dosis in (None, ""):
            self.add_error("dosis", _("Debe ingresar la dosis."))
        if not um:
            self.add_error("um", _("Debe seleccionar la unidad."))

        return cleaned_data

class ActividadInsumoBaseFormSet(BaseInlineFormSet):

    def __init__(self, *args, superficie=None, **kwargs):
        self.superficie = superficie or 1
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()

        for form in self.forms:
            cd = form.cleaned_data
            if not cd or cd.get("DELETE"):
                continue

            producto = cd.get("producto")
            dosis = cd.get("dosis")

            if not producto or dosis is None:
                continue

            cantidad_real = dosis * self.superficie  # igual que guardar_insumos_y_stock

            agg = MovimientoStock.objects.filter(producto=producto).aggregate(
                entradas=Sum("cantidad", filter=Q(tipo=MovimientoStock.Tipo.ENTRADA)),
                salidas=Sum("cantidad", filter=Q(tipo=MovimientoStock.Tipo.SALIDA)),
            )
            disponible = (agg["entradas"] or 0) - (agg["salidas"] or 0)

            if cantidad_real > disponible:
                form.add_error(
                    "dosis",
                    _("Stock insuficiente. Necesario: %(n)s, disponible: %(d)s.")
                    % {"n": cantidad_real, "d": disponible},
                )

ActividadInsumoFormSet = inlineformset_factory(
    ActividadProductiva,
    ActividadInsumo,
    form=ActividadInsumoForm,
    formset=ActividadInsumoBaseFormSet,
    extra=1,
    can_delete=True,
)

class CamposVistoriaForm(BaseForm):
    class Meta:
        model = CamposVistoria
        fields = ["plantas_m2", "malezas", "insectos", "enfermedades", "imagen"]
        widgets = {
            "plantas_m2": forms.NumberInput(attrs={"min": "0"}),
            "malezas": forms.TextInput(),
            "insectos": forms.TextInput(),
            "enfermedades": forms.TextInput(),
        }
        labels = {
            "plantas_m2": _("Plantas por m²"),
            "malezas": _("Malezas"),
            "insectos": _("Insectos"),
            "enfermedades": _("Enfermedades"),
            "imagen": _("Imagen"),
        }

class CamposCosechaForm(BaseForm):
    class Meta:
        model = CamposCosecha
        fields = ["rendimiento", "comentarios_cosecha", "observaciones"]
        widgets = {
            "rendimiento": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "comentarios_cosecha": forms.Textarea(attrs={"rows": 3}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "rendimiento": _("Rendimiento"),
            "comentarios_cosecha": _("Comentarios de cosecha"),
            "observaciones": _("Observaciones"),
        }

class StockFiltroForm(BaseSimpleForm):
    producto = forms.CharField(
        required=False,
        label=_("Producto"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Nombre o código del producto"),
                "class": "form-control",
            }
        ),
    )

    categoria = forms.ModelChoiceField(
        queryset=CategoriaProducto.objects.order_by("nombre"),
        required=False,
        label=_("Categoría"),
        empty_label=_("Todas"),
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    fecha_entrada_desde = forms.DateField(
        required=False,
        label=_("Fecha entrada desde"),
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
            }
        ),
    )

    fecha_entrada_hasta = forms.DateField(
        required=False,
        label=_("Fecha entrada hasta"),
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        fecha_desde = cleaned_data.get("fecha_entrada_desde")
        fecha_hasta = cleaned_data.get("fecha_entrada_hasta")

        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            self.add_error(
                "fecha_entrada_hasta",
                _("La fecha hasta no puede ser menor que la fecha desde."),
            )

        return cleaned_data


UNIDAD_CHOICES = [
    ("L",   "L"),
    ("ML",  "ML"),
    ("KG",  "KG"),
    ("G",   "G"),
    ("TON", "TON"),
    ("UN",  "UN"),
]


class FacturaCompraForm(BaseForm):
    class Meta:
        model = FacturaCompra
        fields = ["numero", "fecha"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"})}
        labels = {"numero": "Número factura", "fecha": "Fecha"}


class FacturaCompraItemForm(forms.Form):

    # ── Campos ocultos del PDF ─────────────────────────────────────────────
    descripcion      = forms.CharField(required=False, widget=forms.HiddenInput())
    unidad_detectada = forms.CharField(required=False, widget=forms.HiddenInput())
    subtotal         = forms.DecimalField(required=False, decimal_places=2,
                                          widget=forms.HiddenInput())

    # ── Producto ───────────────────────────────────────────────────────────
    producto_existente = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        required=False,
        empty_label="— Crear producto nuevo —",
        label=_("Producto existente"),
    )

    crear_nuevo_producto = forms.BooleanField(
        required=False,
        label=_("Crear nuevo"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    # ── Categoría / semilla ────────────────────────────────────────────────
    categoria = forms.ModelChoiceField(
        queryset=CategoriaProducto.objects.all().order_by("nombre"),
        required=False,
        empty_label="---",
        label=_("Categoría"),
    )

    cultivo = forms.ModelChoiceField(
        queryset=Cultivo.objects.all().order_by("nombre"),
        required=False,
        label=_("Cultivo"),
    )

    variedad = forms.ModelChoiceField(
        queryset=Variedad.objects.none(),
        required=False,
        label=_("Variedad"),
    )

    variedad_manual = forms.CharField(
        required=False,
        label=_("Nueva variedad"),
        widget=forms.TextInput(attrs={"placeholder": _("Nombre de la variedad")}),
    )

    # ── Presentación ───────────────────────────────────────────────────────
    presentacion_existente = forms.ModelChoiceField(
        queryset=PresentacionProducto.objects.none(),
        required=False,
        empty_label="— Nueva —",
        label=_("Presentación"),
    )

    nueva_presentacion_nombre = forms.CharField(
        required=False,
        max_length=100,
        label=_("Nombre presentación"),
    )

    # ── Cantidades ─────────────────────────────────────────────────────────
    cantidad = forms.DecimalField(
        min_value=0, decimal_places=3,
        label=_("Cantidad"),
    )

    contenido_por_envase = forms.DecimalField(
        min_value=0, decimal_places=3,
        label=_("Contenido por envase"),
    )

    unidad_medida = forms.ChoiceField(
        choices=UNIDAD_CHOICES,
        label=_("Unidad"),
    )

    precio_unitario = forms.DecimalField(
        min_value=0, decimal_places=2,
        label=_("Precio unit."),
    )

    # ──────────────────────────────────────────────────────────────────────
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa

        # Clases Bootstrap según tipo de widget
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.HiddenInput):
                continue
            if isinstance(w, forms.CheckboxInput):
                continue
            if isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs["class"] = "form-select form-select-sm"
            else:
                w.attrs["class"] = "form-control form-control-sm"

        # Clases específicas para cálculo JS
        self.fields["cantidad"].widget.attrs["class"]            += " cantidad-input"
        self.fields["contenido_por_envase"].widget.attrs["class"] += " contenido-input"
        self.fields["precio_unitario"].widget.attrs["class"]      += " precio-input"

        # Steps
        self.fields["cantidad"].widget.attrs["step"]            = "0.001"
        self.fields["contenido_por_envase"].widget.attrs["step"] = "0.001"
        self.fields["precio_unitario"].widget.attrs["step"]      = "0.01"

        # Queryset productos de la empresa
        if empresa:
            self.fields["producto_existente"].queryset = (
                Producto.objects
                .filter(empresa=empresa, activo=True)
                .select_related("categoria")
                .order_by("nombre")
            )

        # Variedad según cultivo
        cultivo = None
        if self.is_bound:
            cultivo_id = self.data.get(self.add_prefix("cultivo"))
            if cultivo_id:
                cultivo = Cultivo.objects.filter(id=cultivo_id).first()
        else:
            cultivo = self.initial.get("cultivo")

        if cultivo:
            cultivo_id = cultivo.id if hasattr(cultivo, "id") else cultivo
            self.fields["variedad"].queryset = (
                Variedad.objects.filter(cultivo_id=cultivo_id).order_by("nombre")
            )

        # Presentaciones del producto pre-seleccionado
        producto_id = None
        if self.is_bound:
            producto_id = self.data.get(self.add_prefix("producto_existente"))
        elif self.initial.get("producto_existente"):
            p = self.initial["producto_existente"]
            producto_id = p.id if hasattr(p, "id") else p

        if producto_id:
            self.fields["presentacion_existente"].queryset = (
                PresentacionProducto.objects
                .filter(producto_id=producto_id)
                .order_by("nombre")
            )

    # ──────────────────────────────────────────────────────────────────────
    def clean(self):
        cleaned = super().clean()

        cantidad        = cleaned.get("cantidad") or 0
        contenido       = cleaned.get("contenido_por_envase") or 0
        precio          = cleaned.get("precio_unitario") or 0
        categoria       = cleaned.get("categoria")
        cultivo         = cleaned.get("cultivo")
        variedad        = cleaned.get("variedad")
        variedad_manual = (cleaned.get("variedad_manual") or "").strip()
        usar_nuevo      = cleaned.get("crear_nuevo_producto")
        prod_existente  = cleaned.get("producto_existente")
        pres_existente  = cleaned.get("presentacion_existente")

        cleaned["subtotal"]    = cantidad * precio
        cleaned["total_stock"] = cantidad * contenido

        # Si hay producto existente y no se fuerza crear nuevo
        if prod_existente and not usar_nuevo:
            return cleaned

        # Validaciones semilla
        if categoria and "semilla" in categoria.nombre.lower():
            if not cultivo:
                self.add_error("cultivo", _("Debe seleccionar cultivo."))
            if not variedad and not variedad_manual:
                self.add_error("variedad", _("Debe seleccionar variedad o escribir una nueva."))

        # Validaciones presentación nueva
        if not pres_existente:
            if not contenido:
                self.add_error("contenido_por_envase", _("Indicá el contenido del envase."))
            if not cleaned.get("unidad_medida"):
                self.add_error("unidad_medida", _("Seleccioná la unidad de stock."))

        return cleaned


FacturaCompraItemFormSet = formset_factory(
    FacturaCompraItemForm,
    extra=0,
)
