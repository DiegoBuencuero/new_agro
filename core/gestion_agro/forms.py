from decimal import Decimal

from django import forms
from django.forms import ModelForm, inlineformset_factory, formset_factory, BaseInlineFormSet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from agro.models import Unidad
from gestion_agro.funciones_aux import convertir_unidad
from gestion_agro.models import (AreaCampo, Campo, Campana, CicloAgricola, Cultivo, ActividadProductiva, TipoActividad, SubTipoActividad,
                                ActividadInsumo, CamposVistoria, CamposCosecha, CamposInspeccion, Producto, ProductoSemilla,
                                CategoriaProducto, FacturaCompra, Proveedor, PresentacionProducto, Variedad, MovimientoStock, Deposito)


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
        fields = ["nombre", "ciudad", "superficie_ha", "descripcion", "image", "observaciones", "contorno"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 2}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
            "contorno": forms.HiddenInput(),
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

class UnidadForm(BaseForm):
    class Meta:
        model = Unidad
        fields = ["nombre", "abreviatura", "factor_a_base", "requiere_pmg"]

class DepositoForm(BaseForm):
    class Meta:
        model = Deposito
        fields = ["nombre", "tipo", "ciudad", "descripcion", "direccion", "telefono"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 2}),
        }

def _crear_productos_finales_default(cultivo, empresa):
    unidad_kg = Unidad.objects.filter(abreviatura__iexact="kg").first()

    categoria_pf, _categoria_creada = CategoriaProducto.objects.get_or_create(
        codigo="PF", defaults={"nombre": "Producto Final", "es_semilla": False}
    )
    categoria_pfs, _categoria_creada = CategoriaProducto.objects.get_or_create(
        codigo="PFS", defaults={"nombre": "Producto Final - Semilla", "es_semilla": True}
    )

    def _crear(sufijo_nombre, sufijo_codigo, categoria):
        nombre = f"{cultivo.nombre} {sufijo_nombre}"
        base_codigo = f"{cultivo.nombre[:15].upper().replace(' ', '-')}-{sufijo_codigo}"
        codigo = base_codigo
        i = 1
        while Producto.objects.filter(empresa=empresa, codigo=codigo).exists():
            i += 1
            codigo = f"{base_codigo}-{i}"
        return Producto.objects.create(
            empresa=empresa,
            codigo=codigo,
            nombre=nombre,
            categoria=categoria,
            unidad_base=unidad_kg,
            producto_final=True,
            maneja_stock=True,
            activo=True,
        )

    producto_consumo = _crear("Consumo", "CONSUMO", categoria_pf)
    producto_semilla = _crear("Semilla", "SEMILLA", categoria_pfs)

    cultivo.productos_finales.add(producto_consumo, producto_semilla)
    cultivo.producto_default = producto_consumo
    cultivo.save(update_fields=["producto_default"])


class CultivoForm(BaseForm):
    class Meta:
        model = Cultivo
        fields = ["nombre"]

    def save(self, empresa, commit=True):
        cultivo = super().save(commit=False)
        cultivo.empresa = empresa

        if commit:
            cultivo.save()
            _crear_productos_finales_default(cultivo, empresa)

        return cultivo

class CultivoProductoFinalForm(BaseSimpleForm):
    codigo = forms.CharField(
        label=_("Código"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-sm",
            "placeholder": "Ej: TRI-BOLSA-40",
        }),
    )

    detalle = forms.CharField(
        label=_("Detalle"),
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-sm",
            "placeholder": "Ej: Bolsa 40 kg / Fiscalizada / Primera",
        }),
    )

    unidad_base = forms.ModelChoiceField(
        queryset=Unidad.objects.all(),
        label=_("Unidad base"),
        widget=forms.Select(attrs={
            "class": "form-select form-select-sm",
        }),
    )

    dejar_como_default = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            "class": "form-check-input",
        }),
    )

    def save(self, empresa, cultivo):
        detalle = (self.cleaned_data.get("detalle") or "").strip()
        nombre = f"{cultivo.nombre} - {detalle}" if detalle else cultivo.nombre

        codigo = (self.cleaned_data.get("codigo") or "").strip()
        if not codigo:
            codigo = f"PF-{cultivo.nombre[:15].upper().replace(' ', '-')}"

        base_codigo = codigo
        i = 1
        while Producto.objects.filter(empresa=empresa, codigo=codigo).exists():
            i += 1
            codigo = f"{base_codigo}-{i}"

        categoria_producto_final, _categoria_creada = CategoriaProducto.objects.get_or_create(
            codigo="PF", defaults={"nombre": "Producto Final", "es_semilla": False}
        )

        producto = Producto.objects.create(
            empresa=empresa,
            codigo=codigo,
            nombre=nombre,
            categoria=categoria_producto_final,
            unidad_base=self.cleaned_data["unidad_base"],
            producto_final=True,
            maneja_stock=True,
            activo=True,
        )

        cultivo.productos_finales.add(producto)

        if self.cleaned_data.get("dejar_como_default") or not cultivo.producto_default_id:
            cultivo.producto_default = producto
            cultivo.save(update_fields=["producto_default"])

        return producto

class CultivoEditarForm(BaseForm):
    class Meta:
        model = Cultivo
        fields = ["nombre", "producto_default"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["producto_default"].queryset = self.instance.productos_finales.all().order_by("nombre")

class ProductoForm(BaseForm):
    class Meta:
        model = Producto
        fields = ["codigo", "nombre", "categoria", "unidad_base", "precio", "maneja_stock", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["maneja_stock"].widget.attrs["class"] = "form-check-input"
        self.fields["activo"].widget.attrs["class"] = "form-check-input"

class VariedadPMGForm(BaseForm):
    class Meta:
        model   = Variedad
        fields  = ["pmg"]
        widgets = {
            "pmg": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "ej: 150.00"}),
        }
        labels  = {"pmg": _("PMG (g) — Peso de mil granos")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pmg"].required = False

class VariedadSelectWidget(forms.Select):
    """Select que agrega data-pmg a cada opción de variedad."""
    def create_option(self, name, value, label, selected, index, **kwargs):
        option = super().create_option(name, value, label, selected, index, **kwargs)
        if value and hasattr(value, 'instance'):
            pmg = getattr(value.instance, 'pmg', None)
            if pmg:
                option['attrs']['data-pmg'] = str(pmg)
        return option

class ProductoModalForm(BaseForm):
    class Meta:
        model = Producto
        fields = ["codigo", "nombre", "categoria", "unidad_base", "precio", "presentacion_defualt"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["presentacion_defualt"].required = False
        self.fields["precio"].required = False

class PresentacionProductoForm(BaseForm):
    class Meta:
        model = PresentacionProducto
        fields = ["nombre", "contenido", "unidad_contenido", "unidad_factura"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidad_factura"].required = False
class CicloForm(BaseForm):

    class Meta:
        model = CicloAgricola
        fields = "__all__"
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "contorno": forms.HiddenInput(),
        }

    tipo_area = forms.ChoiceField(
        label=_("Área del ciclo"),
        choices=[
            ("todo", _("Todo el campo")),
            ("existente", _("Usar área existente")),
            ("nueva", _("Dibujar nueva área"))
        ],
        initial="todo",
        widget=forms.RadioSelect
    )

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["fecha_inicio"].initial = timezone.localdate()

        self.fields["area"].queryset = AreaCampo.objects.none()

        if empresa:
            self.fields["campo"].queryset = Campo.objects.filter(empresa=empresa).order_by("nombre")
            self.fields["campana"].queryset = Campana.objects.filter(empresa=empresa).order_by("-fecha_desde")
            self.fields["cultivo"].queryset = Cultivo.objects.filter(empresa=empresa).order_by("nombre")
            self.fields["campana"].initial = Campana.objects.filter(empresa=empresa, activa=True).first()

        for field in self.fields.values():
            if isinstance(field.widget, forms.RadioSelect):
                continue
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = f'{field.widget.attrs.get("class","")} {css}'.strip()

        self.fields["tipo_area"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned_data = super().clean()

        tipo_area = cleaned_data.get("tipo_area")
        campo = cleaned_data.get("campo")
        area = cleaned_data.get("area")
        contorno = cleaned_data.get("contorno")

        if tipo_area == "todo" and campo:
            cleaned_data["contorno"] = campo.contorno

        elif tipo_area == "existente":
            if not area:
                self.add_error("area", _("Debe seleccionar un área."))
            else:
                cleaned_data["contorno"] = area.contorno

        elif tipo_area == "nueva" and not contorno:
            self.add_error("contorno", _("Debe dibujar un área."))

        return cleaned_data


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
        else:
            self.fields["campana"].queryset = Campana.objects.none()
            self.fields["campo"].queryset = Campo.objects.none()

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

    def __init__(self, *args, fase=None, ciclo=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound and not self.instance.pk:
            self.initial["fecha"] = timezone.localdate()

        qs = TipoActividad.objects.filter(activo=True)

        # Solo filtrar si la fase existe Y está abierta.
        # Si está cerrada o no hay fase, no excluir nada: una nueva Siembra
        # creará una fase nueva (ver crear_fase_si_corresponde).
        if fase and getattr(fase, "estado", None) != "cerrado":
            tipos_ejecutados = set(
                ActividadProductiva.objects.filter(fase=fase)
                .values_list("tipo_id", flat=True)
                .distinct()
            )

            ids_excluir = set()
            for tipo in TipoActividad.objects.filter(id__in=tipos_ejecutados):
                if tipo.abre_fase:          # Siembra: solo una por fase abierta
                    ids_excluir.add(tipo.id)
                if tipo.requiere_cosecha:   # Cosecha: solo una por fase abierta
                    ids_excluir.add(tipo.id)
                if tipo.requiere_inspeccion:# Inspección: solo una por fase abierta
                    ids_excluir.add(tipo.id)

            if ids_excluir:
                qs = qs.exclude(id__in=ids_excluir)

        self.fields["tipo"].queryset = qs
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
            "dosis":    forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "um":       forms.Select(),
        }
        labels = {
            "producto": _("Producto"),
            "dosis":    _("Dosis"),
            "um":       _("Unidad"),
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
            um = cd.get("um")

            if not producto or dosis is None:
                continue

            cantidad_real = dosis * self.superficie

            movimientos = MovimientoStock.objects.filter(producto=producto).select_related("um")
            ingresado = Decimal("0")
            consumido = Decimal("0")
            conversion_ok = True

            for mov in movimientos:
                try:
                    cantidad = convertir_unidad(mov.cantidad, mov.um, um)
                except (ValueError, TypeError):
                    conversion_ok = False
                    break
                if mov.tipo == "ENTRADA":
                    ingresado += cantidad
                elif mov.tipo == "SALIDA":
                    consumido += cantidad

            if not conversion_ok:
                # No se puede validar stock sin conversión — se deja pasar y el servidor lo controla
                continue

            disponible = ingresado - consumido

            if Decimal(str(cantidad_real)) > disponible:
                form.add_error(
                    "dosis",
                    _("Stock insuficiente. Necesario: %(n)s %(u)s, disponible: %(d)s %(u)s.")
                    % {"n": cantidad_real, "d": disponible, "u": um or ""},
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
    um = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
        label=_("Unidad"),
    )
    # Depósito para el grano de CONSUMO (producto final normal)
    deposito_destino = forms.ModelChoiceField(
        queryset=Deposito.objects.none(),
        required=False,
        label=_("Depósito consumo"),
    )
    # Depósito para el grano de SEMILLA (producción propia certificada)
    deposito_semilla = forms.ModelChoiceField(
        queryset=Deposito.objects.none(),
        required=False,
        label=_("Depósito semilla"),
    )

    def __init__(self, *args, depositos=None, es_semilla=False, **kwargs):
        super().__init__(*args, **kwargs)
        qs = depositos if depositos is not None else Deposito.objects.none()
        self.fields["deposito_destino"].queryset = qs
        self.fields["deposito_semilla"].queryset = qs
        self.fields["rendimiento"].required = True
        if not es_semilla:
            self.fields["deposito_semilla"].widget = forms.HiddenInput()

    def clean_rendimiento(self):
        v = self.cleaned_data.get("rendimiento")
        if v is None or v <= 0:
            raise forms.ValidationError(_("El rendimiento es obligatorio y debe ser mayor a 0."))
        return v

    def clean_um(self):
        v = self.cleaned_data.get("um")
        if not v:
            raise forms.ValidationError(_("Debe seleccionar la unidad de medida del rendimiento."))
        return v

    class Meta:
        model = CamposCosecha
        fields = ["rendimiento", "comentarios_cosecha", "observaciones"]
        widgets = {
            "rendimiento":         forms.NumberInput(attrs={"step": "0.01",  "min": "0.001", "required": "required"}),
            "comentarios_cosecha": forms.Textarea(attrs={"rows": 3}),
            "observaciones":       forms.Textarea(attrs={"rows": 3}),
        }
        
class CamposInspeccionForm(BaseForm):
    class Meta:
        model   = CamposInspeccion
        fields  = ["cant_semilla_mult_ha", "um", "resultado", "responsable"]
        widgets = {
            "cant_semilla_mult_ha": forms.NumberInput(attrs={"step": "1", "min": "0"}),
            "um":                   forms.Select(),
            "resultado":            forms.Select(),
            "responsable":          forms.TextInput(),
        }
        labels = {
            "cant_semilla_mult_ha": _("Semillas aprobadas (por ha)"),
            "um":                   _("Unidad"),
            "resultado":            _("Resultado"),
            "responsable":          _("Responsable"),
        }

    def __init__(self, *args, empresa=None, **kwargs):
        if empresa and empresa.unidad_inspeccion_semilla and not kwargs.get("instance"):
            initial = kwargs.get("initial", {})
            initial.setdefault("um", empresa.unidad_inspeccion_semilla.pk)
            kwargs["initial"] = initial
        super().__init__(*args, **kwargs)
        self.fields["cant_semilla_mult_ha"].required = False
        self.fields["um"].required = False
        self.fields["responsable"].required = False

class StockFiltroForm(BaseSimpleForm):

    producto = forms.CharField(required=False, label=_("Producto"), widget=forms.TextInput(attrs={"placeholder": _("Nombre o código del producto"), "class": "form-control"}))
    categoria = forms.ModelChoiceField(queryset=CategoriaProducto.objects.order_by("nombre"), required=False, label=_("Categoría"), empty_label=_("Todas"), widget=forms.Select(attrs={"class": "form-select"}))
    fecha_entrada_desde = forms.DateField(required=False, label=_("Fecha entrada desde"), widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    fecha_entrada_hasta = forms.DateField(required=False, label=_("Fecha entrada hasta"), widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    def clean(self):
        cleaned_data = super().clean()

        fecha_desde = cleaned_data.get("fecha_entrada_desde")
        fecha_hasta = cleaned_data.get("fecha_entrada_hasta")

        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            self.add_error("fecha_entrada_hasta", _("La fecha hasta no puede ser menor que la fecha desde."))

        return cleaned_data

class FacturaCompraForm(BaseForm):
    class Meta:
        model = FacturaCompra
        fields = ["numero", "fecha", "fecha_vencimiento"]
        widgets = {
            "fecha":             forms.DateInput(attrs={"type": "date"}),
            "fecha_vencimiento": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"numero": "Número factura", "fecha": "Fecha", "fecha_vencimiento": "Vencimiento"}

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
        initial=False,
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
        widget=VariedadSelectWidget(attrs={"class": "form-select form-select-sm", "onchange": "autoFillPMG(this)"}),
    )

    variedad_manual = forms.CharField(
        required=False,
        label=_("Nueva variedad"),
        widget=forms.TextInput(attrs={"placeholder": _("Nombre de la variedad")}),
    )

    pmg = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        label=_("PMG (g/1000 sem)"),
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "Ej: 165", "class": "form-control form-control-sm"}),
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

    unidad_medida = forms.CharField(
        required=False,
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

        self.fields["cantidad"].widget.attrs["class"]             += " cantidad-input"
        self.fields["contenido_por_envase"].widget.attrs["class"] += " contenido-input"
        self.fields["precio_unitario"].widget.attrs["class"]      += " precio-input"

        self.fields["cantidad"].widget.attrs["step"]             = "0.001"
        self.fields["contenido_por_envase"].widget.attrs["step"] = "0.001"
        self.fields["precio_unitario"].widget.attrs["step"]      = "0.01"

        if empresa:
            self.fields["producto_existente"].queryset = (
                Producto.objects
                .filter(empresa=empresa, activo=True)
                .select_related("categoria")
                .order_by("nombre")
            )

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
    def clean_unidad_medida(self):
        valor = self.data.get(self.add_prefix("unidad_medida"))
        if not valor:
            return None
        try:
            return Unidad.objects.get(abreviatura__iexact=valor)
        except Unidad.DoesNotExist:
            raise forms.ValidationError(_("Unidad '%(u)s' no encontrada.") % {"u": valor})

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

        if prod_existente and not usar_nuevo:
            return cleaned

        if categoria and categoria.es_semilla:
            if not cultivo:
                self.add_error("cultivo", _("Debe seleccionar cultivo."))
            if not variedad and not variedad_manual:
                self.add_error("variedad", _("Debe seleccionar variedad o escribir una nueva."))

        if not pres_existente:
            if not contenido:
                self.add_error("contenido_por_envase", _("Indicá el contenido del envase."))
            if not cleaned.get("unidad_medida"):
                self.add_error("unidad_medida", _("Seleccioná la unidad de stock."))

        return cleaned

class FacturaManualItemForm(forms.Form):

    producto_existente = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        required=True,
        empty_label="— Seleccionar —",
        label=_("Producto"),
    )

    presentacion_existente = forms.ModelChoiceField(
        queryset=PresentacionProducto.objects.none(),
        required=True,
        empty_label="— Seleccionar —",
        label=_("Presentación"),
    )

    # Solo se usan para guardar en BD — los llena el AJAX, no el usuario
    cultivo  = forms.ModelChoiceField(queryset=Cultivo.objects.all(), required=False, widget=forms.HiddenInput())
    variedad = forms.ModelChoiceField(queryset=Variedad.objects.all(), required=False, widget=forms.HiddenInput())

    cantidad = forms.DecimalField(
        min_value=0, decimal_places=3,
        label=_("Cantidad"),
        widget=forms.NumberInput(attrs={"step": "0.001", "min": "0"}),
    )

    precio_unitario = forms.DecimalField(
        min_value=0, decimal_places=2,
        label=_("Precio unit."),
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    )

    subtotal = forms.DecimalField(
        required=False, decimal_places=2,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa

        # Clases Bootstrap
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.HiddenInput):
                continue
            if isinstance(w, forms.Select):
                w.attrs["class"] = "form-select form-select-sm"
            else:
                w.attrs["class"] = "form-control form-control-sm"

        if empresa:
            self.fields["producto_existente"].queryset = (
                Producto.objects
                .filter(empresa=empresa, activo=True)
                .select_related("categoria")
                .order_by("nombre")
            )

        # Cargar presentaciones si hay producto pre-seleccionado
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

    def clean(self):
        cleaned = super().clean()
        cantidad = cleaned.get("cantidad") or 0
        precio   = cleaned.get("precio_unitario") or 0
        cleaned["subtotal"] = cantidad * precio
        return cleaned

FacturaManualItemFormSet = formset_factory(FacturaManualItemForm, extra=1)

FacturaCompraItemFormSet = formset_factory(
    FacturaCompraItemForm,
    extra=0,
)
