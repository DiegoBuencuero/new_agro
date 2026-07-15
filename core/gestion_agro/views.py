import base64
import os
import re
import tempfile
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from agro.models import ConversionUM, Unidad
from .funciones_aux import (
    parse_nfe_pdf, br_to_float, _buscar_candidatos, _score, _detectar_contenido_unidad,
    convertir_unidad, registrar_actividad_aux, obtener_valores_costos,
)
from gestion_agro.forms import (
    CampoForm, CampanaForm, CicloForm, CicloFiltroForm, ProductoForm, ProductoModalForm, VariedadPMGForm, PresentacionProductoForm,
    ActividadProductivaForm, ActividadInsumoFormSet, CamposVistoriaForm, CamposCosechaForm, CamposInspeccionForm,
    StockFiltroForm, CultivoProductoFinalForm, FacturaCompraForm, FacturaCompraItemFormSet, FacturaManualItemFormSet,
    CultivoForm, CultivoEditarForm, DepositoForm, UnidadForm,
)
from gestion_agro.models import (
    Campo, AreaCampo, Campana, CicloAgricola, FaseAgricola, SubTipoActividad,
    ActividadProductiva, Producto, TipoActividad, TipoActividadCategoriaProducto,
    ActividadInsumo, CategoriaProducto, MovimientoStock,
    FacturaCompra, Proveedor, PresentacionProducto, FacturaCompraItem, Variedad,
    Cultivo, ProductoSemilla, Deposito, CamposCosecha, CamposInspeccion, Cliente,
)

@login_required
def vista_crear_campo(request):
    empresa = request.user.profile.empresa

    campos = Campo.objects.filter(empresa=empresa)

    if request.method == "POST":
        form = CampoForm(request.POST, request.FILES)
        if form.is_valid():
            campo = form.save(commit=False)
            campo.empresa = empresa
            campo.save()
            messages.success(request, _("Campo creado correctamente"))
            return redirect("vista_crear_campo")
    else:
        form = CampoForm()

    return render(request, "vista_crear_campo.html", {
        "form":    form,
        "campos":  campos,
        "empresa": empresa,
    })

@login_required
def vista_editar_campo(request, id_campo):
    empresa = request.user.profile.empresa
    campos = Campo.objects.filter(empresa=empresa)
    campo = get_object_or_404(Campo, id=id_campo, empresa=empresa)

    if request.method == 'POST':
        form = CampoForm(request.POST, request.FILES, instance=campo)
        if form.is_valid():
            campo = form.save(commit=False)
            if request.POST.get('borrar') == '':
                campo.delete()
            else:
                campo.empresa = empresa
                campo.save()
            return redirect('vista_crear_campo')
        else:
            messages.error(request, form.errors.as_text())
    else:
        form = CampoForm(instance=campo)
    return render(request, 'vista_crear_campo.html', {'form': form, 'campos': campos, 'empresa': empresa, 'modificacion': 'S'})

@login_required
def vista_crear_campana(request):
    empresa = request.user.profile.empresa
    campanas = Campana.objects.filter(empresa=empresa)

    if request.method == "POST":
        form = CampanaForm(request.POST)
        if form.is_valid():
            campana = form.save(commit=False)
            campana.empresa = empresa

            if Campana.objects.filter(
                empresa=empresa,
                nombre=f"{campana.fecha_desde.year}/{campana.fecha_desde.year + 1}"
            ).exists():
                messages.error(request, _("Ya existe una campaña para ese período"))
                return redirect("vista_crear_campana")

            campana.save()
            messages.success(request, _("Campaña creada correctamente"))
            return redirect("vista_crear_campana")
    else:
        form = CampanaForm()

    campanas = Campana.objects.filter(empresa=empresa)

    return render(
        request,
        "vista_crear_campana.html",
        {
            "form": form,
            "campanas": campanas,
            "empresa": empresa,
        },
    )

@login_required
def vista_crear_deposito(request):
    empresa = request.user.profile.empresa

    depositos = Deposito.objects.filter(empresa=empresa)

    if request.method == "POST":
        form = DepositoForm(request.POST)

        if form.is_valid():
            deposito = form.save(commit=False)
            deposito.empresa = empresa
            deposito.save()

            messages.success(request, _("Depósito creado correctamente"))

            return redirect("vista_crear_deposito")
        else:
            messages.error(request, form.errors.as_text())

    else:
        form = DepositoForm()

    return render(
        request,
        "vista_crear_deposito.html",
        {
            "form": form,
            "depositos": depositos,
            "empresa": empresa,
        },
    )

@login_required
def vista_editar_deposito(request, id_deposito):
    empresa = request.user.profile.empresa

    deposito = get_object_or_404(
        Deposito,
        id=id_deposito,
        empresa=empresa
    )

    depositos = Deposito.objects.filter(empresa=empresa)

    if request.method == "POST":

        if "borrar" in request.POST:
            deposito.delete()
            messages.success(request, _("Depósito eliminado correctamente"))
            return redirect("vista_crear_deposito")

        form = DepositoForm(request.POST, instance=deposito)

        if form.is_valid():
            deposito = form.save(commit=False)
            deposito.empresa = empresa
            deposito.save()
            messages.success(request, _("Depósito actualizado correctamente"))
            return redirect("vista_crear_deposito")
        else:
            messages.error(request, form.errors.as_data())

    else:
        form = DepositoForm(instance=deposito)

    return render(request, "vista_crear_deposito.html", {
        "form": form,
        "depositos": depositos,
        "empresa": empresa,
        "modificacion": "S",
    })

@login_required
def vista_editar_campana(request, id_campana):
    empresa = request.user.profile.empresa
    campanas = Campana.objects.filter(empresa=empresa)
    camp = get_object_or_404(Campana, id=id_campana, empresa=empresa)

    if request.method == 'POST':
        form = CampanaForm(request.POST, instance=camp)
        if form.is_valid():
            campana = form.save(commit=False)
            if request.POST.get('borrar') == '':
                campana.delete()
            else:
                campana.save()
            return redirect('vista_crear_campana')
    else:
        form = CampanaForm(instance=camp)
    return render(request, 'vista_crear_campana.html', {'form': form, 'empresa': empresa, 'campanas': campanas, 'modificacion': 'S'})

@login_required
def vista_crear_cultivo(request):
    empresa = request.user.profile.empresa

    cultivos = (
        Cultivo.objects.filter(empresa=empresa)
        .select_related("producto_default")
        .prefetch_related(
            "productos_finales",
            "productos_finales__categoria",
            "productos_finales__unidad_base",
        )
        .order_by("nombre")
    )

    if request.method == "POST":
        form = CultivoForm(request.POST)

        if form.is_valid():
            form.save(empresa=empresa)
            messages.success(request, _("Cultivo creado correctamente"))
            return redirect("vista_crear_cultivo")
        else:
            messages.error(request, _("Revisá los datos del formulario."))
    else:
        form = CultivoForm()

    producto_final_form = CultivoProductoFinalForm()
    producto_final_form.fields["detalle"].required = True

    return render(
        request,
        "vista_crear_cultivo.html",
        {
            "form": form,
            "producto_final_form": producto_final_form,
            "cultivos": cultivos,
            "empresa": empresa,
            "modificacion": False,
        },
    )

@login_required
def vista_editar_cultivo(request, id_cultivo):
    empresa = request.user.profile.empresa

    cultivos = (
        Cultivo.objects.filter(empresa=empresa)
        .select_related("producto_default")
        .prefetch_related(
            "productos_finales",
            "productos_finales__categoria",
            "productos_finales__unidad_base",
        )
        .order_by("nombre")
    )

    cultivo = get_object_or_404(Cultivo, id=id_cultivo, empresa=empresa)

    if request.method == "POST":
        form = CultivoEditarForm(request.POST, instance=cultivo)
        if form.is_valid():
            if "borrar" in request.POST:
                cultivo.delete()
                messages.success(request, _("Cultivo eliminado correctamente."))
            else:
                cultivo = form.save(commit=False)
                cultivo.empresa = empresa
                cultivo.save()
                form.save_m2m()
                messages.success(request, _("Cultivo actualizado correctamente."))

            return redirect("vista_crear_cultivo")
        else:
            messages.error(request, _("Revisá los datos del formulario."))
    else:
        form = CultivoEditarForm(instance=cultivo)

    producto_final_form = CultivoProductoFinalForm()
    producto_final_form.fields["detalle"].required = True

    return render(
        request,
        "vista_crear_cultivo.html",
        {
            "form": form,
            "producto_final_form": producto_final_form,
            "cultivos": cultivos,
            "empresa": empresa,
            "modificacion": True,
            "cultivo_actual": cultivo,
        },
    )

@login_required
def ajax_agregar_producto_final(request, cultivo_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    empresa = request.user.profile.empresa

    try:
        cultivo = Cultivo.objects.get(id=cultivo_id, empresa=empresa)
    except Cultivo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Cultivo no encontrado"}, status=404)

    form = CultivoProductoFinalForm(request.POST)

    if form.is_valid():
        producto = form.save(empresa=empresa, cultivo=cultivo)

        cultivo = (
            Cultivo.objects.filter(id=cultivo.id, empresa=empresa)
            .select_related("producto_default")
            .prefetch_related("productos_finales")
            .first()
        )

        productos = []
        for p in cultivo.productos_finales.all():
            productos.append({
                "id": p.id,
                "nombre": p.nombre,
                "default": cultivo.producto_default_id == p.id,
            })

        return JsonResponse({
            "ok": True,
            "message": "Producto final agregado correctamente",
            "cultivo": {
                "id": cultivo.id,
                "nombre": cultivo.nombre,
                "producto_default_id": cultivo.producto_default_id,
                "producto_default_nombre": cultivo.producto_default.nombre if cultivo.producto_default else "",
                "productos_finales": productos,
                "editar_url": "/cultivos/editar/{}/".format(cultivo.id),
            }
        })

    errores = []
    for field, field_errors in form.errors.items():
        for error in field_errors:
            errores.append(str(field) + ": " + str(error))

    return JsonResponse({
        "ok": False,
        "error": " | ".join(errores)
    }, status=400)

@login_required
def ajax_crear_cultivo(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    empresa = request.user.profile.empresa
    form = CultivoForm(request.POST)

    if form.is_valid():
        cultivo = form.save(empresa=empresa)
        return JsonResponse({
            "ok": True,
            "message": "Cultivo creado correctamente",
            "cultivo": {"id": cultivo.id, "nombre": cultivo.nombre},
        })

    errores = []
    for field, field_errors in form.errors.items():
        for error in field_errors:
            errores.append(str(field) + ": " + str(error))

    return JsonResponse({"ok": False, "error": " | ".join(errores)}, status=400)

@login_required
def ajax_crear_campana(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    empresa = request.user.profile.empresa
    form = CampanaForm(request.POST)

    if form.is_valid():
        campana = form.save(commit=False)
        campana.empresa = empresa

        if Campana.objects.filter(
            empresa=empresa,
            nombre=f"{campana.fecha_desde.year}/{campana.fecha_desde.year + 1}"
        ).exists():
            return JsonResponse({"ok": False, "error": _("Ya existe una campaña para ese período")}, status=400)

        campana.save()
        return JsonResponse({
            "ok": True,
            "message": "Campaña creada correctamente",
            "campana": {"id": campana.id, "nombre": campana.nombre},
        })

    errores = []
    for field, field_errors in form.errors.items():
        for error in field_errors:
            errores.append(str(field) + ": " + str(error))

    return JsonResponse({"ok": False, "error": " | ".join(errores)}, status=400)

@login_required
def ajax_crear_unidad(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    form = UnidadForm(request.POST)

    if form.is_valid():
        unidad = form.save()
        return JsonResponse({
            "ok": True,
            "message": "Unidad creada correctamente",
            "unidad": {"id": unidad.id, "nombre": str(unidad)},
        })

    errores = []
    for field, field_errors in form.errors.items():
        for error in field_errors:
            errores.append(str(field) + ": " + str(error))

    return JsonResponse({"ok": False, "error": " | ".join(errores)}, status=400)

@login_required
def vista_producto(request):
    empresa = request.user.profile.empresa
    productos = Producto.objects.filter(empresa=empresa).select_related("categoria", "unidad_base")
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save(commit=False)
            producto.empresa = empresa
            producto.save()
            messages.success(request, _("Producto guardado correctamente."))
            return redirect('vista_producto')
    else:
        form = ProductoForm()
    return render(request, 'vista_producto.html', {'form': form, 'productos': productos, 'empresa': empresa})

@login_required
def vista_editar_producto(request, id_prod):
    empresa = request.user.profile.empresa
    productos = Producto.objects.filter(empresa=empresa).select_related("categoria", "unidad_base")
    try:
        producto = Producto.objects.get(id=id_prod, empresa=empresa)
    except Producto.DoesNotExist:
        messages.error(request, _("Producto no encontrado."))
        return redirect('vista_producto')

    datos_semilla = getattr(producto, "datos_semilla", None)
    variedad      = datos_semilla.variedad if datos_semilla else None

    if request.method == 'POST':
        form         = ProductoForm(request.POST, instance=producto)
        variedad_form = VariedadPMGForm(request.POST, instance=variedad) if variedad else None

        if form.is_valid():
            if request.POST.get('borrar') == '':
                producto.delete()
                messages.success(request, _("Producto eliminado."))
                return redirect('vista_producto')

            form.save()
            if variedad_form and variedad_form.is_valid():
                variedad_form.save()
            messages.success(request, _("Producto actualizado."))
            return redirect('vista_producto')
    else:
        form          = ProductoForm(instance=producto)
        variedad_form = VariedadPMGForm(instance=variedad) if variedad else None

    return render(request, 'vista_producto.html', {
        'form': form,
        'semilla_form': variedad_form,
        'variedad': variedad,
        'empresa': empresa,
        'productos': productos,
        'prod': producto,
        'modificacion': True,
    })

@login_required
def vista_resumo_economico(request):
    empresa = request.user.profile.empresa
    ciclos_qs = (
        CicloAgricola.objects
        .filter(campo__empresa=empresa)
        .select_related("cultivo", "campo", "campana")
        .prefetch_related("fases__actividades__insumos", "fases__actividades__camposcosecha")
        .order_by("campana__nombre", "cultivo__nombre")
    )

    resumo = []
    for ciclo in ciclos_qs:
        sup = float(ciclo.superficie_ha)
        total_insumos = Decimal("0")
        total_mo      = Decimal("0")
        total_maq     = Decimal("0")
        rend_ha       = Decimal("0")
        cosecha_obj   = None

        for fase in ciclo.fases.all():
            for act in fase.actividades.all():
                for ins in act.insumos.all():
                    total_insumos += ins.costo_total or Decimal("0")
                total_mo  += act.total_mo  or Decimal("0")
                total_maq += act.total_maq or Decimal("0")
                try:
                    cosecha_obj = act.camposcosecha
                    rend_ha = cosecha_obj.rendimiento or Decimal("0")
                except Exception:
                    pass

        costo_total = total_insumos + total_mo + total_maq
        costo_ha    = costo_total / Decimal(str(sup)) if sup else Decimal("0")

        # Precio referencia por cultivo (R$/kg)
        precios = {"Soja": 1.80, "Trigo": 0.85, "Milho": 0.65, "Carinata": 2.20, "Girassol": 2.00}
        precio_kg = Decimal(str(precios.get(ciclo.cultivo.nombre, 1.0)))
        ingreso_ha  = rend_ha * precio_kg
        ingreso_tot = ingreso_ha * Decimal(str(sup))
        margen_ha   = ingreso_ha - costo_ha
        margen_tot  = margen_ha * Decimal(str(sup))
        roi         = float(margen_tot / costo_total * 100) if costo_total else 0

        resumo.append({
            "ciclo":            ciclo,
            "sup":              sup,
            "rend_ha":          float(rend_ha),
            "costo_insumos_ha": float(total_insumos / Decimal(str(sup))) if sup else 0,
            "costo_mo_ha":      float(total_mo  / Decimal(str(sup))) if sup else 0,
            "costo_maq_ha":     float(total_maq / Decimal(str(sup))) if sup else 0,
            "costo_ha":         float(costo_ha),
            "costo_total":      float(costo_total),
            "ingreso_ha":       float(ingreso_ha),
            "ingreso_total":    float(ingreso_tot),
            "margen_ha":        float(margen_ha),
            "margen_total":     float(margen_tot),
            "roi":              roi,
            "precio_kg":        float(precio_kg),
        })

    return render(request, "vista_resumo_economico.html", {
        "resumo":  resumo,
        "empresa": empresa,
    })

@login_required
def vista_lista_ciclos(request):
    empresa = request.user.profile.empresa

    ciclos = (
        CicloAgricola.objects.filter(
            campo__empresa=empresa,
            activa=True
        )
        .select_related("campo", "campana", "cultivo")
        .order_by("-fecha_inicio")
    )

    form = CicloFiltroForm(empresa=empresa)

    context = {
        "ciclos": ciclos,
        "form": form,
        "empresa": empresa,
    }

    return render(request, "vista_lista_ciclos.html", context)

@login_required
def ajax_get_ciclos_data(request):
    empresa = request.user.profile.empresa

    ciclos = CicloAgricola.objects.filter(
        campo__empresa=empresa
    ).select_related(
        "campo", "campana", "cultivo"
    ).order_by("-fecha_inicio")

    campana_id = request.GET.get("campana")
    campo_id = request.GET.get("campo")
    cultivo_id = request.GET.get("cultivo")
    estado = request.GET.get("estado")

    if campana_id:
        ciclos = ciclos.filter(campana_id=campana_id)

    if campo_id:
        ciclos = ciclos.filter(campo_id=campo_id)

    if cultivo_id:
        ciclos = ciclos.filter(cultivo_id=cultivo_id)

    if estado == "activo":
        ciclos = ciclos.filter(activa=True)
    elif estado == "cerrado":
        ciclos = ciclos.filter(activa=False)

    lista_data = []

    for ciclo in ciclos:
        item = {
            "id": ciclo.id,
            "campo": ciclo.campo.nombre if ciclo.campo else "",
            "campana": str(ciclo.campana) if ciclo.campana else "",
            "nombre_lote": ciclo.nombre_lote if ciclo.nombre_lote else "",
            "cultivo": str(ciclo.cultivo) if ciclo.cultivo else "",
            "superficie_ha": str(ciclo.superficie_ha) if ciclo.superficie_ha is not None else "",
            "fecha_inicio": ciclo.fecha_inicio.strftime("%d/%m/%Y") if ciclo.fecha_inicio else "",
            "estado": "cerrado" if ciclo.fecha_fin else "activo",
            "estado_label": "Cerrado" if ciclo.fecha_fin else "Activo",
            "detalle_url": reverse("vista_detalle_ciclo", args=[ciclo.id])
        }
        lista_data.append(item)

    return JsonResponse({
        "response": 1,
        "data": lista_data
    })

@login_required
def vista_crear_ciclo(request):
    empresa = getattr(request.user.profile, "empresa", None)

    if not empresa:
        messages.error(request, _("El usuario no tiene una empresa asociada."))
        return redirect("index")

    if request.method == "POST":
        form = CicloForm(request.POST, empresa=empresa)

        if form.is_valid():
            ciclo = form.save(commit=False)

            campo = ciclo.campo
            campana = ciclo.campana
            cultivo = ciclo.cultivo

            numero_lote = (
                CicloAgricola.objects
                .filter(campo=campo, campana=campana)
                .count() + 1
            )

            ciclo.nombre_lote = _("Lote-%(numero)s") % {
                "numero": numero_lote
            }
            ciclo.producto_final = cultivo.producto_default
            ciclo.activa = True

            try:
                ciclo.save()
            except ValidationError as e:
                for lista_errores in e.message_dict.values():
                    for error in lista_errores:
                        messages.error(request, error)
            else:
                messages.success(
                    request,
                    _("Ciclo creado correctamente. Ahora podés registrar actividades.")
                )
                return redirect("vista_lista_ciclos")
    else:
        form = CicloForm(empresa=empresa)

    context = {
        "form": form,
        "empresa": empresa,
        "modificacion": False,
        "cultivo_form": CultivoForm(),
        "campana_form": CampanaForm(),
        "producto_final_form": CultivoProductoFinalForm(),
        "unidad_form": UnidadForm(),
    }
    return render(request, "vista_crear_ciclo.html", context)

@login_required
def ajax_areas_por_campo(request):

    empresa=request.user.profile.empresa
    campo_id=request.GET.get("campo_id")

    if not empresa or not campo_id:
        return JsonResponse({
            "ok":False,
            "areas":[]
        })

    try:
        campo=Campo.objects.get( id=campo_id, empresa=empresa )

    except Campo.DoesNotExist:
        return JsonResponse({ "ok":False, "areas":[] })

    areas_json=[]

    areas=AreaCampo.objects.filter(campo=campo,  contorno__isnull=False ).exclude(contorno="").order_by("nombre")

    for area in areas:
        areas_json.append({
            "id":area.id,
            "nombre":area.nombre,
            "superficie_ha":str(area.superficie_ha or ""),
            "contorno":area.contorno
        })

    return JsonResponse({
        "ok":True,
        "campo_superficie_ha":str(campo.superficie_ha or ""),
        "campo_contorno":campo.contorno,
        "areas":areas_json
    })

@login_required
def ajax_info_cultivo(request):
    empresa = getattr(request.user.profile, "empresa", None)
    cultivo_id = request.GET.get("cultivo_id")

    if not empresa:
        return JsonResponse({"ok": False, "error": _("Usuario sin empresa asociada.")}, status=400)

    if not cultivo_id:
        return JsonResponse({"ok": False, "error": _("Cultivo no informado.")}, status=400)

    try:
        cultivo = Cultivo.objects.select_related("producto_default").get(
            id=cultivo_id,
            empresa=empresa
        )
    except Cultivo.DoesNotExist:
        return JsonResponse({"ok": False, "error": _("Cultivo no encontrado.")}, status=404)

    return JsonResponse({
        "ok": True,
        "cultivo": {
            "id": cultivo.id,
            "nombre": cultivo.nombre,
        },
        "producto_default": {
            "id": cultivo.producto_default.id,
            "nombre": cultivo.producto_default.nombre,
        } if cultivo.producto_default else None,
    })

@login_required
def vista_detalle_ciclo(request, id_ciclo):
    empresa = request.user.profile.empresa

    ciclo = get_object_or_404(
        CicloAgricola.objects.select_related("campo", "campana", "cultivo"),
        campo__empresa=empresa,
        id=id_ciclo,
    )

    fases = FaseAgricola.objects.filter(ciclo=ciclo).order_by("fecha_inicio")

    insumos_qs = ActividadInsumo.objects.select_related("producto", "um").order_by("id")

    actividades = (
        ActividadProductiva.objects
        .filter(fase__ciclo=ciclo)
        .select_related("fase", "tipo", "subtipo")
        .prefetch_related(
            Prefetch("insumos", queryset=insumos_qs),
            "camposcosecha",
            "camposinspeccion__um",
        )
        .order_by("fecha", "id")
    )

    # desglose de costos
    costo_mo_ciclo  = sum(act.total_mo  or Decimal("0") for act in actividades)
    costo_maq_ciclo = sum(act.total_maq or Decimal("0") for act in actividades)
    costo_ins_ciclo = ActividadInsumo.objects.filter(
        actividad__fase__ciclo=ciclo
    ).aggregate(t=Coalesce(Sum("costo_total"), Decimal("0")))["t"]
    costo_total_ciclo = costo_mo_ciclo + costo_maq_ciclo + costo_ins_ciclo

    ha = ciclo.superficie_ha or Decimal("1")
    costo_ha_ciclo  = costo_total_ciclo / ha
    costo_mo_ha     = costo_mo_ciclo    / ha
    costo_maq_ha    = costo_maq_ciclo   / ha
    costo_ins_ha    = costo_ins_ciclo   / ha

    fecha_fin_real = (
        fases.filter(estado="cerrado")
        .order_by("-fecha_fin")
        .values_list("fecha_fin", flat=True)
        .first()
    )

    # precio de mercado en tiempo real (misma lógica que el dashboard)
    from agro.views import _stooq_price, _usd_brl, _STOOQ
    precio_saco = Decimal("0")
    try:
        nom = (ciclo.cultivo.nombre or "").lower() if ciclo.cultivo else ""
        if "soja" in nom:
            key, kg_bushel = "soja", 27.2155
        elif "maíz" in nom or "maiz" in nom:
            key, kg_bushel = "maiz", 25.4012
        elif "trigo" in nom:
            key, kg_bushel = "trigo", 27.2155
        else:
            key = None
        if key:
            cents, _fecha = _stooq_price(_STOOQ[key])
            usd, _fecha_usd, _fuente_usd = _usd_brl()
            if cents and usd:
                usd_bushel = cents / 100
                precio_saco = Decimal(str(round(usd_bushel * (60 / kg_bushel) * usd, 2)))
    except Exception:
        pass

    sacos_equilibrio_ha = Decimal("0")
    if precio_saco and costo_ha_ciclo:
        sacos_equilibrio_ha = costo_ha_ciclo / precio_saco

    rendimiento_esperado_sacos = getattr(ciclo, 'rendimiento_esperado_sacos', None)

    context = {
        "ciclo": ciclo,
        "fases": fases,
        "actividades": actividades,
        "costo_total_ciclo": costo_total_ciclo,
        "costo_ha_ciclo":    costo_ha_ciclo,
        "costo_mo_ha":       costo_mo_ha,
        "costo_maq_ha":      costo_maq_ha,
        "costo_ins_ha":      costo_ins_ha,
        "precio_saco": precio_saco,
        "sacos_equilibrio_ha": sacos_equilibrio_ha,
        "rendimiento_esperado_sacos": rendimiento_esperado_sacos,
        "fecha_fin_real": fecha_fin_real,
    }

    return render(request, "vista_detalle_ciclo.html", context)


@login_required
def vista_editar_ciclo(request, id_ciclo):
    empresa = request.user.profile.empresa
    ciclo   = get_object_or_404(CicloAgricola, id=id_ciclo, campo__empresa=empresa)

    if request.method == "POST":
        nombre_lote   = request.POST.get("nombre_lote", "").strip()
        superficie_ha = request.POST.get("superficie_ha")
        fecha_inicio  = request.POST.get("fecha_inicio")
        activa        = request.POST.get("activa") == "1"

        try:
            ciclo.nombre_lote   = nombre_lote or ciclo.nombre_lote
            if superficie_ha:
                ciclo.superficie_ha = Decimal(superficie_ha)
            if fecha_inicio:
                ciclo.fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
            ciclo.activa = activa
            ciclo.save()
            messages.success(request, _("Ciclo actualizado."))
            return redirect("vista_lista_ciclos")
        except ValidationError as e:
            for lista_errores in e.message_dict.values():
                for error in lista_errores:
                    messages.error(request, error)
        except Exception as e:
            messages.error(request, _("Error: %(error)s") % {"error": e})

    return render(request, "vista_editar_ciclo.html", {"ciclo": ciclo, "empresa": empresa})


@login_required
@require_POST
def ajax_eliminar_ciclo(request, id_ciclo):
    empresa = request.user.profile.empresa
    ciclo   = get_object_or_404(CicloAgricola, id=id_ciclo, campo__empresa=empresa)
    try:
        ciclo.delete()
        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

@login_required
def ajax_subtipos_tipo_actividad(request):
    tipo_id = request.GET.get("tipo_id")
    if not tipo_id:
        return JsonResponse({"ok": False, "subtipos": []})
    
    try:
        tipo = TipoActividad.objects.get(id=tipo_id)
    except TipoActividad.DoesNotExist:
        return JsonResponse({"ok": False, "subtipos": []})

    subtipos = SubTipoActividad.objects.filter(
        tipo_actividad_id=tipo_id, activo=True
    ).order_by("nombre")

    data = [{"id": subtipo.id, "nombre": subtipo.nombre} for subtipo in subtipos]

    return JsonResponse({
        "ok": True,
        "subtipos": data,
        "requiere_mo":          tipo.requiere_mo,
        "requiere_maq":         tipo.requiere_maq,
        "requiere_insumo":      tipo.requiere_insumo,
        "requiere_vist":        tipo.requiere_vist,
        "requiere_cosecha":     tipo.requiere_cosecha,
        "requiere_inspeccion":  tipo.requiere_inspeccion,
        "es_siembra":           tipo.nombre_es.lower() == "siembra",
    })

@login_required
def vista_agregar_actividad(request, id_ciclo):
    empresa = request.user.profile.empresa
    depositos = Deposito.objects.filter(empresa=empresa)

    ciclo = CicloAgricola.objects.filter(id=id_ciclo, campo__empresa=empresa,).first()

    if not ciclo:
        messages.error(request, _("El ciclo no existe."))
        return redirect("vista_lista_ciclos")

    fase = (FaseAgricola.objects.filter(ciclo=ciclo).order_by("-fecha_inicio", "-id").first())

    # Si la fase quedo abierta pero ya tiene una actividad cierra_fase (ej: Cosecha
    # guardada antes de que fallara el cierre), la cerramos ahora para que el formulario
    # muestre todos los tipos disponibles (incluyendo Siembra para una nueva fase).
    if fase and fase.estado != "cerrado":
        acto_cierre = (ActividadProductiva.objects.filter(fase=fase, tipo__cierra_fase=True).order_by("-fecha").first())
        if acto_cierre:
            fase.estado = "cerrado"
            fase.fecha_fin = acto_cierre.fecha
            fase.save()

    # ── Inspección aprobada y flag semilla — calculado UNA vez para GET y POST ──

    inspeccion_aprobada = (
        CamposInspeccion.objects
        .filter(actividad__fase__ciclo=ciclo, resultado=CamposInspeccion.Resultado.APROBADO)
        .select_related("um")
        .order_by("-actividad__fecha", "-id")
        .first()
    )
    es_semilla = bool(inspeccion_aprobada) or bool(
        ciclo.producto_final and
        ciclo.producto_final.categoria and
        ciclo.producto_final.categoria.es_semilla
    )

    # PMG de la variedad usada en siembra
    pmg_siembra = None
    if inspeccion_aprobada and inspeccion_aprobada.um and inspeccion_aprobada.um.requiere_pmg:
        try:
            _insumo_s = ActividadInsumo.objects.filter(
                actividad__fase__ciclo=ciclo,
                actividad__tipo__nombre_es__iexact="siembra",
                producto__categoria__es_semilla=True,
            ).select_related("producto__datos_semilla__variedad").first()
            pmg_siembra = float(_insumo_s.producto.datos_semilla.variedad.pmg)
        except Exception:
            pmg_siembra = None

    # kg semilla estimados desde inspección aprobada (fijo, no depende del rendimiento)
    kg_semilla_estimado = None
    if inspeccion_aprobada and inspeccion_aprobada.cant_semilla_mult_ha and ciclo.superficie_ha:
        cant_ha    = inspeccion_aprobada.cant_semilla_mult_ha
        superficie = ciclo.superficie_ha
        if inspeccion_aprobada.um and inspeccion_aprobada.um.requiere_pmg and pmg_siembra:
            kg_semilla_estimado = float(cant_ha * superficie * Decimal(str(pmg_siembra)) / Decimal("1000000"))
        else:
            factor = Decimal("1")
            if inspeccion_aprobada.um and ciclo.producto_final:
                try:
                    conv = ConversionUM.objects.get(
                        um_origen=inspeccion_aprobada.um,
                        um_destino=ciclo.producto_final.unidad_base,
                    )
                    factor = conv.factor
                except ConversionUM.DoesNotExist:
                    pass
            kg_semilla_estimado = float(cant_ha * superficie * factor)

    # depósito default para cosecha (semilla y consumo)
    dep_cosecha_default = None
    if ciclo.producto_final:
        dep_cosecha_default = ciclo.producto_final.deposito_default or empresa.deposito_producto_final_default

    if request.method == "POST":
        actividad_form    = ActividadProductivaForm(request.POST, fase=fase, ciclo=ciclo)
        insumo_formset    = ActividadInsumoFormSet(
            request.POST, prefix="insumos",
            form_kwargs={"empresa": empresa}, superficie=ciclo.superficie_ha,
        )
        vistoria_form     = CamposVistoriaForm(request.POST, request.FILES, prefix="vistoria")
        cosecha_form      = CamposCosechaForm(
            request.POST, prefix="cosecha",
            depositos=depositos, es_semilla=es_semilla,
        )
        inspeccion_form   = CamposInspeccionForm(request.POST, prefix="inspeccion", empresa=empresa)

        if actividad_form.is_valid():
            tipo = actividad_form.cleaned_data["tipo"]
            forms_validos = True

            if tipo.requiere_insumo and not insumo_formset.is_valid():
                forms_validos = False
                for form in insumo_formset:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Insumo - {field}: {error}")
                for error in insumo_formset.non_form_errors():
                    messages.error(request, f"Insumo: {error}")

            if tipo.requiere_vist and not vistoria_form.is_valid():
                forms_validos = False

            if tipo.requiere_cosecha and not cosecha_form.is_valid():
                forms_validos = False
                for field, errs in cosecha_form.errors.items():
                    for e in errs:
                        lbl = getattr(cosecha_form.fields.get(field), "label", field) or field
                        messages.error(request, f"Cosecha — {lbl}: {e}")

            if tipo.requiere_inspeccion and not inspeccion_form.is_valid():
                forms_validos = False

            if forms_validos:
                ok, resultado = registrar_actividad_aux(
                    ciclo=ciclo, fase=fase, empresa=empresa,
                    actividad_form=actividad_form,
                    insumo_formset=insumo_formset,
                    vistoria_form=vistoria_form,
                    cosecha_form=cosecha_form,
                    inspeccion_form=inspeccion_form,
                )
                if ok:
                    msg = _("Actividad registrada e inicio de fase generado.") if resultado["inicio_fase"] else _("Actividad registrada correctamente.")
                    messages.success(request, msg)
                    return redirect("vista_detalle_ciclo", id_ciclo=ciclo.id)
                messages.error(request, resultado)
        else:
            messages.error(request, _("Hay errores en el formulario."))

    else:
        actividad_form  = ActividadProductivaForm(
            initial={"fecha": timezone.localdate()}, fase=fase, ciclo=ciclo,
        )
        insumo_formset  = ActividadInsumoFormSet(
            prefix="insumos", form_kwargs={"empresa": empresa}, superficie=ciclo.superficie_ha,
        )
        vistoria_form   = CamposVistoriaForm(prefix="vistoria")
        cosecha_form    = CamposCosechaForm(
            prefix="cosecha", depositos=depositos, es_semilla=es_semilla,
            initial={
                "deposito_destino": dep_cosecha_default,
                "deposito_semilla": dep_cosecha_default,
            },
        )
        inspeccion_form = CamposInspeccionForm(prefix="inspeccion", empresa=empresa)

    context = {
        "ciclo":               ciclo,
        "actividad_form":      actividad_form,
        "insumo_formset":      insumo_formset,
        "vistoria_form":       vistoria_form,
        "cosecha_form":        cosecha_form,
        "inspeccion_form":     inspeccion_form,
        "es_semilla":           es_semilla,
        "inspeccion_aprobada":  inspeccion_aprobada,
        "pmg_siembra":          pmg_siembra,
        "kg_semilla_estimado":  kg_semilla_estimado,
    }

    return render(request, "vista_agregar_actividad.html", context)

@login_required
def ajax_productos_por_actividad(request):
    tipo_id = request.GET.get("tipo_id")
    subtipo_id = request.GET.get("subtipo_id")
    ciclo_id = request.GET.get("ciclo_id")

    if not tipo_id:
        return JsonResponse({"ok": False, "productos": []})

    empresa = request.user.profile.empresa

    try:
        tipo = TipoActividad.objects.get(id=tipo_id, activo=True)
    except TipoActividad.DoesNotExist:
        return JsonResponse({"ok": False, "productos": []})

    configuraciones = TipoActividadCategoriaProducto.objects.filter(
        tipo_actividad=tipo,
        activo=True,
    )

    if subtipo_id:
        configuraciones_subtipo = configuraciones.filter(subtipo_actividad_id=subtipo_id)
        if configuraciones_subtipo.exists():
            configuraciones = configuraciones_subtipo
        else:
            configuraciones = configuraciones.filter(subtipo_actividad__isnull=True)
    else:
        configuraciones = configuraciones.filter(subtipo_actividad__isnull=True)

    categoria_ids = configuraciones.values_list("categoria_producto_id", flat=True)

    if categoria_ids:
        productos = Producto.objects.filter(
            empresa=empresa,
            activo=True,
            maneja_stock=True,
            categoria_id__in=categoria_ids
        )
    else:
        productos = Producto.objects.filter(
            empresa=empresa,
            activo=True,
            maneja_stock=True
        )

    # filtrar semillas por cultivo del ciclo
    ciclo = None
    if ciclo_id:
        ciclo = CicloAgricola.objects.filter(id=ciclo_id).first()

    if ciclo:
        productos_semilla = productos.filter(
            categoria__es_semilla=True,
            datos_semilla__cultivo=ciclo.cultivo
        )
        productos_no_semilla = productos.filter(categoria__es_semilla=False)
        productos = (productos_semilla | productos_no_semilla).distinct()

    productos = productos.select_related("unidad_base").order_by("nombre")

    data = []
    for producto in productos.select_related("categoria", "datos_semilla__variedad"):
        pmg = None
        if producto.categoria.es_semilla:
            ds = getattr(producto, "datos_semilla", None)
            if ds and ds.variedad:
                pmg = float(ds.variedad.pmg) if ds.variedad.pmg else None
        data.append({
            "id":                producto.id,
            "nombre":            producto.nombre,
            "unidad_id":         producto.unidad_base_id,
            "unidad_abreviatura": producto.unidad_base.abreviatura if producto.unidad_base else "",
            "es_semilla":        producto.categoria.es_semilla,
            "pmg":               pmg,
        })

    return JsonResponse({"ok": True, "productos": data})

@login_required
def ajax_valores_actividad(request):
    tipo_id = request.GET.get("tipo_id")
    subtipo_id = request.GET.get("subtipo_id")
    ciclo_id = request.GET.get("ciclo_id")

    if not tipo_id or not ciclo_id:
        return JsonResponse({
            "ok": False,
            "cantidad_hombre": "",
            "valor_hombre": "",
            "cantidad_h_maq": "",
            "valor_h_maq": "",
        })

    try:
        tipo = TipoActividad.objects.get(id=tipo_id, activo=True)
    except TipoActividad.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "cantidad_hombre": "",
            "valor_hombre": "",
            "cantidad_h_maq": "",
            "valor_h_maq": "",
        })

    subtipo = None
    if subtipo_id:
        try:
            subtipo = SubTipoActividad.objects.get(
                id=subtipo_id,
                activo=True,
                tipo_actividad=tipo,
            )
        except SubTipoActividad.DoesNotExist:
            subtipo = None

    try:
        ciclo = CicloAgricola.objects.select_related("campo__empresa").get(id=ciclo_id)
    except CicloAgricola.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "cantidad_hombre": "",
            "valor_hombre": "",
            "cantidad_h_maq": "",
            "valor_h_maq": "",
        })

    empresa = ciclo.campo.empresa

    v_mo, v_mq, c_mo, c_mq = obtener_valores_costos(tipo, subtipo, empresa)

    return JsonResponse({
        "ok": True,
        "cantidad_hombre": str(v_mo) if v_mo is not None else "",
        "valor_hombre": str(c_mo) if c_mo is not None else "",
        "cantidad_h_maq": str(v_mq) if v_mq is not None else "",
        "valor_h_maq": str(c_mq) if c_mq is not None else "",
    })

@login_required
@require_POST
def ajax_eliminar_actividad(request, actividad_id):
    empresa = request.user.profile.empresa
    try:
        act = ActividadProductiva.objects.get(
            id=actividad_id,
            fase__ciclo__campo__empresa=empresa
        )
        act.delete()
        return JsonResponse({"ok": True})
    except ActividadProductiva.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Actividad no encontrada"}, status=404)


@login_required
@require_POST
def ajax_eliminar_insumo(request, insumo_id):
    empresa = request.user.profile.empresa
    try:
        insumo = ActividadInsumo.objects.get(
            id=insumo_id,
            actividad__fase__ciclo__campo__empresa=empresa
        )
        insumo.delete()
        return JsonResponse({"ok": True})
    except ActividadInsumo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Insumo no encontrado"}, status=404)


@login_required
@require_POST
def ajax_editar_insumo(request, insumo_id):
    empresa = request.user.profile.empresa
    try:
        insumo = ActividadInsumo.objects.get(
            id=insumo_id,
            actividad__fase__ciclo__campo__empresa=empresa
        )
    except ActividadInsumo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Insumo no encontrado"}, status=404)

    try:
        nueva_dosis = Decimal(request.POST.get("dosis", "0"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Dosis inválida"}, status=400)

    insumo.dosis = nueva_dosis
    sup = insumo.actividad.fase.ciclo.superficie_ha
    if sup:
        insumo.cantidad_real = nueva_dosis * sup
        insumo.costo_total   = (insumo.costo_ha or Decimal("0")) * sup if insumo.costo_ha else None
    insumo.save()

    um = insumo.um.abreviatura if insumo.um else ""
    return JsonResponse({
        "ok": True,
        "dosis_fmt": f"{float(nueva_dosis):.2f} {um}/ha",
    })


@login_required
def vista_lista_stock(request):
    empresa = request.user.profile.empresa
    form = StockFiltroForm(request.GET or None)

    # Filtro por safra (campana)
    campanas       = Campana.objects.filter(empresa=empresa).order_by("-nombre")
    campana_id     = request.GET.get("campana") or None
    campana_sel    = None
    ciclos_safra   = None  # IDs de ciclos de la safra seleccionada

    if campana_id:
        campana_sel = campanas.filter(id=campana_id).first()
        if campana_sel:
            ciclos_safra = list(
                CicloAgricola.objects.filter(campana=campana_sel, campo__empresa=empresa)
                .values_list("id", flat=True)
            )

    productos = (
        Producto.objects.select_related("categoria", "unidad_base")
        .filter(empresa=empresa)
        .order_by("nombre")
    )

    categorias = CategoriaProducto.objects.order_by("nombre")

    producto_txt = ""
    categoria = None
    fecha_desde = None
    fecha_hasta = None

    if form.is_valid():
        producto_txt = (form.cleaned_data.get("producto") or "").strip()
        categoria = form.cleaned_data.get("categoria")
        fecha_desde = form.cleaned_data.get("fecha_entrada_desde")
        fecha_hasta = form.cleaned_data.get("fecha_entrada_hasta")

    if producto_txt:
        productos = productos.filter(
            Q(nombre__icontains=producto_txt) |
            Q(codigo__icontains=producto_txt)
        ).distinct()

    if categoria:
        productos = productos.filter(categoria=categoria)

    lista_insumos = []
    lista_productos_finales = []

    total_ingresado = Decimal("0")
    total_consumido = Decimal("0")
    total_restante = Decimal("0")

    total_ingresado_insumos = Decimal("0")
    total_consumido_insumos = Decimal("0")
    total_restante_insumos = Decimal("0")

    total_ingresado_finales = Decimal("0")
    total_consumido_finales = Decimal("0")
    total_restante_finales = Decimal("0")
    total_cosechado_real = Decimal("0")  # solo origen cosecha

    for producto in productos:
        movimientos = MovimientoStock.objects.filter(producto=producto).select_related(
            "um", "deposito_origen", "deposito_destino"
        )

        if fecha_desde:
            movimientos = movimientos.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            movimientos = movimientos.filter(fecha__lte=fecha_hasta)

        # Filtro por safra: solo movimientos de actividades de ciclos de esa campaña
        if ciclos_safra is not None:
            movimientos = movimientos.filter(
                Q(actividad__fase__ciclo__id__in=ciclos_safra) |
                Q(cosecha__actividad__fase__ciclo__id__in=ciclos_safra)
            )

        if not movimientos.exists():
            continue

        ingresado = Decimal("0")
        consumido = Decimal("0")
        unidad_base = producto.unidad_base

        depositos_cantidad = {}
        depositos_obj = {}

        for mov in movimientos:
            cantidad = convertir_unidad(mov.cantidad, mov.um, unidad_base)

            if mov.tipo == "ENTRADA":
                ingresado += cantidad
                if mov.deposito_destino_id:
                    dep_id = mov.deposito_destino_id
                    depositos_obj[dep_id] = mov.deposito_destino
                    depositos_cantidad[dep_id] = depositos_cantidad.get(dep_id, Decimal("0")) + cantidad

            elif mov.tipo == "SALIDA":
                consumido += cantidad
                if mov.deposito_origen_id:
                    dep_id = mov.deposito_origen_id
                    depositos_obj[dep_id] = mov.deposito_origen
                    depositos_cantidad[dep_id] = depositos_cantidad.get(dep_id, Decimal("0")) - cantidad

        por_deposito = [
            {"deposito": depositos_obj[dep_id], "cantidad": cant}
            for dep_id, cant in depositos_cantidad.items()
            if cant != 0
        ]

        restante = ingresado - consumido

        item = {
            "obj":          producto,
            "ingresado":    ingresado,
            "consumido":    consumido,
            "restante":     restante,
            "por_deposito": por_deposito,
        }

        total_ingresado += ingresado
        total_consumido += consumido
        total_restante += restante

        if producto.producto_final:
            # Separar movimientos por destino (M=Semilla, C=Consumo, None=compras/otros)
            movs_list = list(movimientos.select_related("um", "deposito_origen", "deposito_destino", "cosecha"))

            def _build_final_item(destino_cod, destino_label):
                ing = Decimal("0")
                con = Decimal("0")
                deps_cant = {}
                deps_obj  = {}
                for mov in movs_list:
                    cantidad = convertir_unidad(mov.cantidad, mov.um, unidad_base)
                    # Entradas de cosecha solo si coincide destino; compras van a C (o sin destino)
                    if mov.tipo == "ENTRADA":
                        if mov.cosecha_id:
                            if mov.destino == destino_cod:
                                ing += cantidad
                                if mov.deposito_destino_id:
                                    deps_obj[mov.deposito_destino_id]  = mov.deposito_destino
                                    deps_cant[mov.deposito_destino_id] = deps_cant.get(mov.deposito_destino_id, Decimal("0")) + cantidad
                        elif mov.destino == destino_cod:
                            # Entrada de transferencia interna — solo ajusta depósito
                            if mov.deposito_destino_id:
                                deps_obj[mov.deposito_destino_id]  = mov.deposito_destino
                                deps_cant[mov.deposito_destino_id] = deps_cant.get(mov.deposito_destino_id, Decimal("0")) + cantidad
                        elif not mov.destino and destino_cod == "C":
                            # Compras y otros ingresos sin destino van a Consumo
                            ing += cantidad
                            if mov.deposito_destino_id:
                                deps_obj[mov.deposito_destino_id]  = mov.deposito_destino
                                deps_cant[mov.deposito_destino_id] = deps_cant.get(mov.deposito_destino_id, Decimal("0")) + cantidad
                    elif mov.tipo == "VENTA" and mov.destino == destino_cod:
                        # Venta real: descuenta del consumido y del depósito origen
                        con += cantidad
                        if mov.deposito_origen_id:
                            deps_obj[mov.deposito_origen_id]  = mov.deposito_origen
                            deps_cant[mov.deposito_origen_id] = deps_cant.get(mov.deposito_origen_id, Decimal("0")) - cantidad
                    elif mov.tipo == "SALIDA":
                        # Transferencia interna: solo ajusta depósitos, no cuenta como venta
                        if mov.destino == destino_cod or (not mov.destino and destino_cod == "C"):
                            if mov.deposito_origen_id:
                                deps_obj[mov.deposito_origen_id]  = mov.deposito_origen
                                deps_cant[mov.deposito_origen_id] = deps_cant.get(mov.deposito_origen_id, Decimal("0")) - cantidad

                if ing == 0 and con == 0:
                    return None

                por_dep = [{"deposito": deps_obj[d], "cantidad": c} for d, c in deps_cant.items() if c != 0]
                return {
                    "obj":              producto,
                    "destino":          destino_cod,
                    "destino_label":    destino_label,
                    "ingresado":        ing,
                    "consumido":        con,
                    "restante":         ing - con,
                    "por_deposito":     por_dep,
                    "cosechado_cosecha": ing if any(m.cosecha_id and m.destino == destino_cod and m.tipo == "ENTRADA" for m in movs_list) else Decimal("0"),
                }

            item_m = _build_final_item("M", "Semilla")
            item_c = _build_final_item("C", "Consumo")

            for it in [item_m, item_c]:
                if it:
                    lista_productos_finales.append(it)
                    total_ingresado_finales += it["ingresado"]
                    total_consumido_finales += it["consumido"]
                    total_restante_finales  += it["restante"]
                    total_cosechado_real    += it["cosechado_cosecha"]
        else:
            # Insumos: semillas compradas, herbicidas, fertilizantes, etc.
            lista_insumos.append(item)
            total_ingresado_insumos += ingresado
            total_consumido_insumos += consumido
            total_restante_insumos += restante

    lista_productos = lista_insumos + lista_productos_finales

    depositos = Deposito.objects.filter(empresa=empresa).order_by("nombre")
    clientes_venta = Cliente.objects.filter(empresa=empresa).order_by("razon_social")

    context = {
        "form": form,
        "categorias": categorias,
        "depositos": depositos,
        "campanas":    campanas,
        "campana_sel": campana_sel,

        # lista general
        "productos": lista_productos,
        "total_productos": len(lista_productos),

        # listas separadas
        "insumos": lista_insumos,
        "productos_finales":  lista_productos_finales,
        "clientes_venta":     clientes_venta,

        # totales generales
        "total_ingresado": total_ingresado,
        "total_consumido": total_consumido,
        "total_restante": total_restante,

        # totales insumos
        "total_ingresado_insumos": total_ingresado_insumos,
        "total_consumido_insumos": total_consumido_insumos,
        "total_restante_insumos": total_restante_insumos,

        # totales productos finales
        "total_ingresado_finales": total_ingresado_finales,
        "total_consumido_finales": total_consumido_finales,
        "total_restante_finales": total_restante_finales,
        "total_cosechado_real": total_cosechado_real,
    }

    return render(request, "vista_lista_stock.html", context)

@login_required
def vista_movimientos_producto(request, producto_id):
    empresa = request.user.profile.empresa

    producto = get_object_or_404(
        Producto,
        id=producto_id,
        empresa=empresa,
    )

    movimientos = MovimientoStock.objects.filter(
        producto=producto
    ).select_related(
        "um",
        "factura_item__factura",
        "actividad_item__actividad__fase__ciclo__campo",
        "actividad_item__actividad__fase__ciclo__cultivo",
        "actividad_item__actividad__fase__ciclo__campana",
    ).order_by("fecha", "id")

    fecha_desde = request.GET.get("fecha_desde")
    fecha_hasta = request.GET.get("fecha_hasta")
    tipo = request.GET.get("tipo")
    origen = request.GET.get("origen")
    texto = request.GET.get("texto", "").strip().lower()

    if fecha_desde:
        movimientos = movimientos.filter(fecha__date__gte=fecha_desde)

    if fecha_hasta:
        movimientos = movimientos.filter(fecha__date__lte=fecha_hasta)

    if tipo in ["ENTRADA", "SALIDA"]:
        movimientos = movimientos.filter(tipo=tipo)

    movimientos_lista = []
    saldo = Decimal("0")
    total_entrada = Decimal("0")
    total_salida = Decimal("0")

    for mov in movimientos:
        cantidad = convertir_unidad(mov.cantidad, mov.um, producto.unidad_base)
        if cantidad is None:
            cantidad = Decimal("0")

        origen_mov = "Manual"
        observacion = "-"

        if mov.cosecha_id:
            # PRODUCCIÓN PROPIA — grano de cosecha (semilla o consumo)
            cosecha_act = mov.cosecha.actividad if mov.cosecha else None
            if cosecha_act and cosecha_act.fase and cosecha_act.fase.ciclo:
                c = cosecha_act.fase.ciclo
                partes = [p for p in [
                    c.campo.nombre if c.campo else "",
                    c.nombre_lote or "",
                    str(c.cultivo) if c.cultivo else "",
                ] if p]
                observacion = " - ".join(partes) or "-"
                tipo_porcion = _("Semilla") if mov.es_semilla_cosecha else _("Consumo")
                if mov.deposito_destino_id:
                    observacion += f" [{tipo_porcion}] → {mov.deposito_destino}"
                else:
                    observacion += f" [{tipo_porcion}]"
            else:
                observacion = "Cosecha"
            origen_mov = "Producción propia"

        elif mov.actividad_item:
            origen_mov = "Actividad"
            actividad  = mov.actividad_item.actividad
            if actividad and actividad.fase and actividad.fase.ciclo:
                c = actividad.fase.ciclo
                partes = [p for p in [
                    c.campo.nombre if c.campo else "",
                    c.nombre_lote or "",
                    str(c.cultivo) if c.cultivo else "",
                ] if p]
                observacion = " - ".join(partes) or "-"

        elif mov.factura_item and mov.factura_item.factura:
            numero = mov.factura_item.factura.numero or ""
            origen_mov  = "Compra"
            observacion = f"Fact: {numero}" if numero else "-"

        else:
            origen_mov  = "Manual"
            observacion = "-"

        if origen and origen != origen_mov:
            continue

        if texto and texto not in observacion.lower():
            continue

        entrada = Decimal("0")
        salida = Decimal("0")

        if mov.tipo == "ENTRADA":
            entrada = cantidad
            saldo += cantidad
            total_entrada += cantidad
        else:
            salida = cantidad
            saldo -= cantidad
            total_salida += cantidad

        movimientos_lista.append({
            "id": mov.id,
            "fecha": mov.fecha,
            "tipo": mov.tipo,
            "origen": origen_mov,
            "observacion": observacion,
            "entrada": entrada,
            "salida": salida,
            "saldo": saldo,
            "precio_unitario": mov.precio_unitario,
        })

    context = {
        "producto": producto,
        "movimientos": movimientos_lista,
        "total_entrada": total_entrada,
        "total_salida": total_salida,
        "saldo_actual": saldo,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "tipo": tipo,
        "origen": origen,
        "texto": request.GET.get("texto", "").strip(),
    }

    return render(request, "vista_movimientos_producto.html", context)

@login_required
def vista_lista_facturas(request):
    empresa = request.user.profile.empresa

    facturas = FacturaCompra.objects.filter(
        empresa=empresa
    ).select_related("proveedor").order_by("-fecha", "-id")

    return render(request, "tem_facturas/vista_lista_facturas.html", {
        "facturas": facturas
    })

@login_required
def vista_cargar_factura(request):
    return render(request, "tem_facturas/vista_cargar_factura.html")

@login_required
def vista_cargar_factura_manual(request):
    empresa = request.user.profile.empresa

    def _context_base(factura_form, formset, proveedor_seleccionado=0, deposito_seleccionado=None):
        return {
            "factura_form":           factura_form,
            "formset":                formset,
            "proveedores":            Proveedor.objects.filter(empresa=empresa).order_by("razon_social"),
            "productos":              Producto.objects.filter(empresa=empresa, activo=True).order_by("nombre"),
            "categorias":             CategoriaProducto.objects.all().order_by("nombre"),
            "unidades":               Unidad.objects.all().order_by("abreviatura"),
            "cultivos":               Cultivo.objects.all().order_by("nombre"),
            "depositos":              Deposito.objects.filter(empresa=empresa).order_by("nombre"),
            "deposito_default":       deposito_seleccionado or empresa.deposito_insumos_default,
            "proveedor_seleccionado": proveedor_seleccionado,
        }

    TEMPLATE = "tem_facturas/vista_cargar_factura_manual.html"

    if request.method == "POST":
        factura_form = FacturaCompraForm(request.POST)
        formset = FacturaManualItemFormSet(
            request.POST, prefix="items",
            form_kwargs={"empresa": empresa}
        )

        # ── Agregar ítem ──
        if "agregar_item" in request.POST:
            data = request.POST.copy()
            data["items-TOTAL_FORMS"] = int(data.get("items-TOTAL_FORMS", 0)) + 1
            formset = FacturaManualItemFormSet(
                data, prefix="items",
                form_kwargs={"empresa": empresa}
            )
            return render(request, TEMPLATE, _context_base(
                FacturaCompraForm(request.POST),
                formset,
                int(request.POST.get("proveedor", 0) or 0),
            ))

        # ── Guardar factura ──
        if "ok" in request.POST:
            if factura_form.is_valid() and formset.is_valid():
                deposito_destino = Deposito.objects.filter(
                    id=request.POST.get("deposito_destino"),
                    empresa=empresa
                ).first() or empresa.deposito_insumos_default

                with transaction.atomic():
                    factura = factura_form.save(commit=False)
                    factura.empresa      = empresa
                    factura.proveedor_id = request.POST.get("proveedor")
                    factura.total        = sum(
                        f.cleaned_data.get("subtotal") or 0
                        for f in formset if f.cleaned_data
                    )
                    factura.save()

                    for form in formset:
                        if not form.cleaned_data:
                            continue

                        producto     = form.cleaned_data["producto_existente"]
                        presentacion = form.cleaned_data["presentacion_existente"]
                        cantidad     = form.cleaned_data["cantidad"]
                        precio       = form.cleaned_data["precio_unitario"]
                        subtotal     = form.cleaned_data["subtotal"]

                        cantidad_base = cantidad * presentacion.contenido

                        item = FacturaCompraItem.objects.create(
                            factura=factura,
                            producto=producto,
                            presentacion=presentacion,
                            cantidad_facturada=cantidad,
                            cantidad_base=cantidad_base,
                            precio_unitario=precio,
                            subtotal=subtotal,
                        )

                        MovimientoStock.objects.create(
                            producto=producto,
                            tipo=MovimientoStock.Tipo.ENTRADA,
                            cantidad=cantidad_base,
                            um=presentacion.unidad_contenido,
                            factura_item=item,
                            fecha=factura.fecha,
                            precio_unitario=precio,
                            deposito_destino=deposito_destino,
                        )

                messages.success(request, _("Factura cargada correctamente."))
                return redirect("vista_lista_facturas")
            else:
                messages.error(request, _("Revisá los errores del formulario."))

    else:
        factura_form = FacturaCompraForm()
        formset = FacturaManualItemFormSet(prefix="items", form_kwargs={"empresa": empresa})

    return render(request, TEMPLATE, _context_base(factura_form, formset))

@login_required
def ajax_presentaciones_producto(request):
    producto_id = request.GET.get("producto_id")
    if not producto_id:
        return JsonResponse({"ok": False}, status=400)
    try:
        producto = Producto.objects.select_related(
            "categoria",
            "datos_semilla__cultivo",
            "datos_semilla__variedad",
        ).get(id=producto_id, empresa=request.user.profile.empresa)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False}, status=404)

    presentaciones = list(
        PresentacionProducto.objects.filter(producto=producto).values("id", "nombre")
    )

    # Datos de semilla si aplica
    semilla = None
    if hasattr(producto, "datos_semilla"):
        semilla = {
            "cultivo_id":    producto.datos_semilla.cultivo_id,
            "cultivo_nombre": producto.datos_semilla.cultivo.nombre,
            "variedad_id":   producto.datos_semilla.variedad_id,
            "variedad_nombre": producto.datos_semilla.variedad.nombre,
        }

    return JsonResponse({
        "ok":            True,
        "presentaciones": presentaciones,
        "default_id":    producto.presentacion_defualt_id,
        "es_semilla":    semilla is not None,
        "semilla":       semilla,
    })

@login_required
def ajax_variedades_cultivo(request):
    cultivo_id = request.GET.get("cultivo_id")
    if not cultivo_id:
        return JsonResponse({"ok": False, "variedades": []})
    variedades = list(
        Variedad.objects.filter(cultivo_id=cultivo_id).order_by("nombre").values("id", "nombre", "pmg")
    )
    return JsonResponse({"ok": True, "variedades": variedades})

@login_required
def ajax_crear_producto(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)

    empresa = request.user.profile.empresa
    modo_cultivo = request.POST.get("producto_final") == "1"

    form = ProductoModalForm(request.POST)
    if not form.is_valid():
        errores = [f"{f}: {e}" for f, errs in form.errors.items() for e in errs]
        return JsonResponse({"ok": False, "error": " | ".join(errores)}, status=400)

    producto = form.save(commit=False)
    producto.empresa = empresa
    producto.producto_final = modo_cultivo
    producto.save()

    es_semilla = producto.categoria.es_semilla
    cultivo = None
    variedad = None

    if es_semilla:
        cultivo_id = request.POST.get("cultivo")
        variedad_id = request.POST.get("variedad")
        variedad_nueva = (request.POST.get("variedad_nueva") or "").strip()

        if not cultivo_id:
            producto.delete()
            return JsonResponse({"ok": False, "error": "Seleccioná el cultivo."}, status=400)

        try:
            cultivo = Cultivo.objects.get(id=cultivo_id, empresa=empresa)
        except Cultivo.DoesNotExist:
            producto.delete()
            return JsonResponse({"ok": False, "error": "Cultivo no encontrado."}, status=400)

        # FACTURA / flujo normal
        if not modo_cultivo:
            if variedad_id:
                try:
                    variedad = Variedad.objects.get(id=variedad_id, cultivo=cultivo)
                except Variedad.DoesNotExist:
                    producto.delete()
                    return JsonResponse({"ok": False, "error": "La variedad no pertenece al cultivo."}, status=400)
            elif variedad_nueva:
                variedad, _ = Variedad.objects.get_or_create(
                    cultivo=cultivo,
                    nombre=variedad_nueva
                )
            # Guardar PMG si fue enviado (aplica a variedad existente o nueva)
            pmg_raw = request.POST.get("pmg")
            if variedad and pmg_raw:
                try:
                    variedad.pmg = Decimal(pmg_raw)
                    variedad.save(update_fields=["pmg"])
                except Exception:
                    pass
            else:
                producto.delete()
                return JsonResponse({"ok": False, "error": "Seleccioná o escribí una variedad."}, status=400)

        # CREAR CULTIVO / producto final
        else:
            variedad, _ = Variedad.objects.get_or_create(
                cultivo=cultivo,
                nombre="GENERAL"
            )

        producto.nombre = (request.POST.get("nombre") or producto.nombre).strip()
        producto.save(update_fields=["nombre"])

        try:
            ProductoSemilla.objects.create(
                producto=producto,
                cultivo=cultivo,
                variedad=variedad
            )
        except Exception as e:
            producto.delete()
            return JsonResponse({"ok": False, "error": str(e)}, status=400)

    pres_nombre = (request.POST.get("pres_nombre") or "").strip()
    pres_contenido = request.POST.get("pres_contenido")
    pres_unidad_id = request.POST.get("pres_unidad")

    presentacion = None
    if pres_nombre and pres_contenido and pres_unidad_id:
        try:
            unidad_contenido = Unidad.objects.get(id=pres_unidad_id)
            presentacion = PresentacionProducto.objects.create(
                producto=producto,
                nombre=pres_nombre,
                contenido=pres_contenido,
                unidad_contenido=unidad_contenido,
                unidad_factura=unidad_contenido.abreviatura,
            )
            producto.presentacion_defualt = presentacion
            producto.save(update_fields=["presentacion_defualt"])
        except Exception:
            presentacion = None

    return JsonResponse({
        "ok": True,
        "id": producto.id,
        "nombre": producto.nombre,
        "producto_final": producto.producto_final,
        "es_semilla": es_semilla,
        "semilla": {
            "cultivo_id": cultivo.id,
            "cultivo_nombre": cultivo.nombre,
            "variedad_id": variedad.id,
            "variedad_nombre": variedad.nombre,
        } if es_semilla and cultivo and variedad else None,
        "presentacion": {
            "id": presentacion.id,
            "nombre": presentacion.nombre,
        } if presentacion else None,
    })

@login_required
def ajax_crear_producto_desde_cultivo(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)

    empresa = request.user.profile.empresa

    codigo = (request.POST.get("codigo") or "").strip()
    cultivo_id = request.POST.get("cultivo")

    if not codigo:
        return JsonResponse({"ok": False, "error": "Completá el código."}, status=400)

    if not cultivo_id:
        return JsonResponse({"ok": False, "error": "Seleccioná el cultivo."}, status=400)

    try:
        cultivo = Cultivo.objects.get(id=cultivo_id, empresa=empresa)
    except Cultivo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Cultivo no encontrado."}, status=400)

    categoria_semilla = CategoriaProducto.objects.filter(es_semilla=True).first()
    if not categoria_semilla:
        return JsonResponse({"ok": False, "error": "No existe una categoría de semilla configurada."}, status=400)

    unidad_kg = Unidad.objects.filter(abreviatura__iexact="kg").first()
    if not unidad_kg:
        return JsonResponse({"ok": False, "error": "No existe una unidad KG configurada."}, status=400)

    nombre = f"SEMILLA DE {cultivo.nombre}".strip().upper()

    try:
        producto = Producto.objects.create(
            empresa=empresa,
            codigo=codigo,
            nombre=nombre,
            categoria=categoria_semilla,
            unidad_base=unidad_kg,
            producto_final=True,
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    try:
        variedad, _ = Variedad.objects.get_or_create(
            cultivo=cultivo,
            nombre="GENERAL"
        )

        ProductoSemilla.objects.create(
            producto=producto,
            cultivo=cultivo,
            variedad=variedad
        )

        presentacion = PresentacionProducto.objects.create(
            producto=producto,
            nombre="Kilogramo",
            contenido=1,
            unidad_contenido=unidad_kg,
            unidad_factura=unidad_kg.abreviatura,
        )

        producto.presentacion_defualt = presentacion
        producto.save(update_fields=["presentacion_defualt"])

    except Exception as e:
        producto.delete()
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    return JsonResponse({
        "ok": True,
        "id": producto.id,
        "nombre": producto.nombre,
        "producto_final": True,
        "es_semilla": True,
        "semilla": {
            "cultivo_id": cultivo.id,
            "cultivo_nombre": cultivo.nombre,
            "variedad_id": variedad.id,
            "variedad_nombre": variedad.nombre,
        },
        "presentacion": {
            "id": presentacion.id,
            "nombre": presentacion.nombre,
        }
    })

@login_required
def ajax_unidades_por_base(request):
    unidad_base_id = request.GET.get("unidad_base_id")
    if not unidad_base_id:
        return JsonResponse({"ok": False}, status=400)
    try:
        unidad_base = Unidad.objects.get(id=unidad_base_id)
    except Unidad.DoesNotExist:
        return JsonResponse({"ok": False}, status=404)

    conversiones = ConversionUM.objects.filter(um_destino=unidad_base).select_related("um_origen")
    lista = [{"id": c.um_origen.id, "abreviatura": c.um_origen.abreviatura, "factor": str(c.factor)} for c in conversiones]

    return JsonResponse({
        "ok":                True,
        "unidad_base_id":    unidad_base.id,
        "unidad_base_abrev": unidad_base.abreviatura,
        "unidades":          lista,
    })

@login_required
def ajax_crear_presentacion(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    empresa = request.user.profile.empresa
    try:
        producto = Producto.objects.get(id=request.POST.get("producto_id"), empresa=empresa)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Producto no encontrado"}, status=404)
    form = PresentacionProductoForm(request.POST)
    if form.is_valid():
        pres = form.save(commit=False)
        pres.producto = producto
        pres.save()
        return JsonResponse({"ok": True, "id": pres.id, "nombre": pres.nombre})
    errores = []
    for field, errors in form.errors.items():
        for error in errors:
            errores.append(field + ": " + error)
    return JsonResponse({"ok": False, "error": " | ".join(errores)}, status=400)

@login_required
def vista_procesar_pdf_factura(request):
    if request.method != "POST":
        return redirect("vista_cargar_factura")

    pdf_file = request.FILES.get("pdf_file")
    if not pdf_file:
        messages.error(request, _("No se ha seleccionado ningún archivo PDF."))
        return redirect("vista_cargar_factura")

    pdf_content = pdf_file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_content)
        tmp_path = tmp.name

    try:
        datos = parse_nfe_pdf(tmp_path)

        if not datos.get("items"):
            messages.error(request, _("No se encontraron productos en la factura."))
            return redirect("vista_cargar_factura")

        total = sum(
            Decimal(str(br_to_float(i.get("v_total")) or 0))
            for i in datos["items"]
        )

        fecha_html = ""
        if datos.get("fecha_emision"):
            try:
                fecha_html = datetime.strptime(
                    datos["fecha_emision"], "%d/%m/%Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                fecha_html = ""

        request.session["factura_temporal"] = {
            "items": datos["items"],
            "nombre_archivo": pdf_file.name,
            "proveedor_data": datos.get("proveedor"),
            "datos_factura": {
                "numero_factura": datos.get("numero_nfe"),
                "fecha_emision": fecha_html,
                "total": str(total),
            },
            "pdf_base64": base64.b64encode(pdf_content).decode("utf-8"),
            "pdf_nombre": pdf_file.name,
        }
        return redirect("vista_revisar_factura")

    except Exception as e:
        messages.error(request, _("Error procesando factura: %(error)s") % {"error": str(e)})
        return redirect("vista_cargar_factura")

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def _br_to_float(valor):
    if not valor:
        return None
    try:
        return float(str(valor).replace(".", "").replace(",", "."))
    except ValueError:
        return None

@login_required
def vista_revisar_factura(request):

    factura_temp = request.session.get("factura_temporal")
    if not factura_temp:
        messages.warning(request, _("No hay factura cargada."))
        return redirect("vista_cargar_factura")

    empresa = request.user.profile.empresa
    if not empresa:
        messages.error(request, _("No tiene empresa asignada."))
        return redirect("vista_cargar_factura")

    items          = factura_temp["items"]
    proveedor_data = factura_temp.get("proveedor_data", "")
    datos_factura  = factura_temp["datos_factura"]

    # ── Proveedor ────────────────────────────────────────────────────────
    nombre    = (proveedor_data or "").upper()[:255] or "PROVEEDOR SIN IDENTIFICAR"
    documento = re.sub(r"[^\d]", "", proveedor_data or "") or "00000000000"

    proveedor_obj, _creado = Proveedor.objects.get_or_create(
        empresa=empresa,
        razon_social=nombre,
        defaults={"identificador": documento},
    )
    request.session["proveedor_seleccionado"] = proveedor_obj.id

    # ── Formulario cabecera ───────────────────────────────────────────────
    cabecera_form = FacturaCompraForm(initial={
        "numero": datos_factura.get("numero_factura"),
        "fecha":  datos_factura.get("fecha_emision"),
    })

    # ── Datos iniciales + matching ────────────────────────────────────────
    initial_data = []
    match_info   = []

    for item in items:
        desc         = item.get("descricao", "")
        unid_factura = item.get("unidade", "")
        cant         = _br_to_float(item.get("quantidade", 0)) or 0
        p_u          = _br_to_float(item.get("v_unit", 0)) or 0
        contenido, unidad, pres_nombre = _detectar_contenido_unidad(desc, unid_factura)

        # Buscar candidatos — filtro simple por la primera palabra significativa
        palabras = [p for p in desc.split() if len(p) >= 4]
        candidatos = []

        if palabras:
            todos = Producto.objects.filter(
                empresa=empresa,
                activo=True,
                nombre__icontains=palabras[0]   # filtra por la primera palabra
            ).select_related("categoria")[:30]

            for prod in todos:
                s = _score(desc, prod)
                if s >= 35:
                    candidatos.append({"producto": prod, "score": s})

            candidatos.sort(key=lambda x: x["score"], reverse=True)
            candidatos = candidatos[:4]

        mejor_score    = candidatos[0]["score"] if candidatos else 0
        mejor_producto = candidatos[0]["producto"] if candidatos else None

        presentaciones = []
        if mejor_producto:
            presentaciones = list(
                PresentacionProducto.objects.filter(producto_id=mejor_producto.id).order_by("nombre")
            )

        pres_match = next(
            (p for p in presentaciones if p.unidad_factura.upper() == unid_factura.upper()),
            None,
    )

        # Si el candidato es semilla, pre-cargar cultivo para que el form muestre variedades
        cultivo_inicial = None
        if mejor_producto and mejor_producto.categoria and mejor_producto.categoria.es_semilla:
            try:
                ps = mejor_producto.datos_semilla
                cultivo_inicial = ps.cultivo
            except Exception:
                pass

        initial_data.append({
            "descripcion":               desc,
            "unidad_detectada":          unid_factura,
            "cantidad":                  cant,
            "precio_unitario":           p_u,
            "subtotal":                  cant * p_u,
            "contenido_por_envase":      contenido,
            "unidad_medida":             unidad,
            "nueva_presentacion_nombre": f"Envase {contenido} {unidad}",
            "producto_existente":        mejor_producto.id if mejor_producto else None,
            "presentacion_existente":    pres_match.id if pres_match else None,
            "cultivo":                   cultivo_inicial,
            # Versiones con punto decimal para <input type="number">
            "cantidad_num":              format(cant, 'g') if cant else '',
            "precio_num":                format(p_u, 'g') if p_u else '',
            "contenido_num":             format(contenido, 'g') if contenido else '',
        })

        match_info.append({
            "candidatos":  candidatos,           # lista [{"producto", "score"}]
            "score":       mejor_score,
            "label": (
                "alto"   if mejor_score >= 75 else
                "medio"  if mejor_score >= 50 else
                "bajo"   if mejor_score >= 35 else
                "ninguno"
            ),
            "presentaciones": presentaciones,
        })

    formset = FacturaCompraItemFormSet(
        initial=initial_data,
        prefix="item",
        form_kwargs={"empresa": empresa},
    )

    # Pre-cargar presentaciones y variedades en el form según el candidato principal
    for i, form in enumerate(formset):
        prod = initial_data[i].get("producto_existente")
        if prod:
            form.fields["presentacion_existente"].queryset = (
                PresentacionProducto.objects.filter(producto_id=prod).order_by("nombre")
            )
        cultivo_ini = initial_data[i].get("cultivo")
        if cultivo_ini:
            cultivo_id = cultivo_ini.id if hasattr(cultivo_ini, "id") else cultivo_ini
            form.fields["variedad"].queryset = (
                Variedad.objects.filter(cultivo_id=cultivo_id).order_by("nombre")
            )

    context = {
        "cabecera_form":   cabecera_form,
        "formset":         formset,
        "items_con_match": list(zip(formset, match_info, initial_data)),
        "items":           items,
        "nombre_archivo":  factura_temp["nombre_archivo"],
        "datos_factura":   datos_factura,
        "proveedor":       proveedor_obj,
        "empresa_usuario": empresa,
        "categorias":      CategoriaProducto.objects.all().order_by("nombre"),
        "depositos":       Deposito.objects.filter(empresa=empresa).order_by("nombre"),
        "deposito_default": empresa.deposito_insumos_default,
    }

    return render(request, "tem_facturas/vista_revisar_factura.html", context)

@login_required
@transaction.atomic
def vista_confirmar_factura(request):
    if request.method != "POST":
        return redirect("vista_revisar_factura")

    factura_temp = request.session.get("factura_temporal")
    if not factura_temp:
        messages.error(request, _("Sesión expirada."))
        return redirect("vista_cargar_factura")

    empresa = request.user.profile.empresa
    proveedor_id = (
        request.session.get("proveedor_seleccionado")
        or request.POST.get("proveedor")
    )

    try:
        proveedor = Proveedor.objects.get(id=proveedor_id, empresa=empresa)
    except Proveedor.DoesNotExist:
        messages.error(request, _("Proveedor no encontrado."))
        return redirect("vista_revisar_factura")

    _dep_id = request.POST.get("deposito_destino") or None
    deposito_destino = (
        Deposito.objects.filter(id=_dep_id, empresa=empresa).first()
        if _dep_id else None
    ) or empresa.deposito_insumos_default

    cabecera_form = FacturaCompraForm({
        "numero": request.POST.get("numero_factura"),
        "fecha":  request.POST.get("fecha"),
    })

    formset = FacturaCompraItemFormSet(
        request.POST,
        prefix="item",
        form_kwargs={"empresa": empresa},
    )

    if not cabecera_form.is_valid() or not formset.is_valid():
        messages.error(request, _("Hay errores en la factura. Revisá los campos marcados."))
        _idata_err = []
        for raw in factura_temp.get("items", []):
            cant = _br_to_float(raw.get("quantidade", 0)) or 0
            p_u  = _br_to_float(raw.get("v_unit", 0)) or 0
            contenido, unidad, _pn = _detectar_contenido_unidad(
                raw.get("descricao", ""), raw.get("unidade", "")
            )
            _idata_err.append({
                "descripcion":    raw.get("descricao", ""),
                "unidad_medida":  unidad,
                "cantidad_num":   format(cant, 'g') if cant else '',
                "precio_num":     format(p_u,  'g') if p_u  else '',
                "contenido_num":  format(contenido, 'g') if contenido else '',
            })
        return render(request, "tem_facturas/vista_revisar_factura.html", {
            "cabecera_form":   cabecera_form,
            "formset":         formset,
            "items_con_match": [
                (f, {"score": 0, "label": "ninguno", "candidatos": [], "presentaciones": []}, idata)
                for f, idata in zip(formset, _idata_err)
            ],
            "items":           factura_temp["items"],
            "nombre_archivo":  factura_temp["nombre_archivo"],
            "datos_factura":   factura_temp["datos_factura"],
            "proveedor":       proveedor,
            "empresa_usuario": empresa,
        })

    # ── Verificar duplicada ────────────────────────────────────────────────
    numero_factura = request.POST.get("numero_factura")
    if FacturaCompra.objects.filter(
        empresa=empresa,
        proveedor=proveedor,
        numero=numero_factura
    ).exists():
        messages.warning(
            request,
            _("La factura %(numero)s ya fue ingresada para este proveedor.") % {"numero": numero_factura}
        )
        request.session.pop("factura_temporal", None)
        request.session.pop("proveedor_seleccionado", None)
        return redirect("vista_lista_facturas")

    # ── Guardar cabecera ───────────────────────────────────────────────────
    factura = cabecera_form.save(commit=False)
    factura.empresa   = empresa
    factura.proveedor = proveedor
    factura.total     = Decimal("0.00")

    # ── Guardar PDF desde sesión ───────────────────────────────────────────
    pdf_base64 = factura_temp.get("pdf_base64")
    pdf_nombre = factura_temp.get("pdf_nombre", "factura.pdf")
    if pdf_base64:
        factura.archivo_pdf.save(
            pdf_nombre,
            ContentFile(base64.b64decode(pdf_base64)),
            save=False
        )
    factura.save()

    total_factura = Decimal("0.00")

    for i, form in enumerate(formset):
        cd = form.cleaned_data
        if not cd:
            continue

        usar_nuevo           = cd.get("crear_nuevo_producto")
        prod_existente       = cd.get("producto_existente")
        pres_existente       = cd.get("presentacion_existente")

        descripcion          = (cd.get("descripcion") or "").strip()
        unidad_detectada     = (cd.get("unidad_detectada") or "UN").strip()
        categoria            = cd.get("categoria")
        cultivo              = cd.get("cultivo")
        variedad             = cd.get("variedad")
        variedad_manual      = (cd.get("variedad_manual") or "").strip()

        cantidad_envases     = cd["cantidad"]
        contenido_por_envase = cd["contenido_por_envase"]
        unidad_medida        = cd["unidad_medida"]
        precio_unitario      = cd["precio_unitario"]
        subtotal             = cd.get("subtotal") or (cantidad_envases * precio_unitario)

        # ── Resolver producto ──────────────────────────────────────────────
        if prod_existente and not usar_nuevo:
            producto = prod_existente
        else:
            es_semilla = categoria and categoria.es_semilla

            if es_semilla and cultivo:
                variedad_obj = variedad
                if not variedad_obj and variedad_manual:
                    variedad_obj, creado = Variedad.objects.get_or_create(
                        cultivo=cultivo, nombre=variedad_manual
                    )
                if variedad_obj:
                    nombre_producto = f"{descripcion[:180]} - {cultivo.nombre} {variedad_obj.nombre}"
                else:
                    nombre_producto = descripcion[:255]
            else:
                variedad_obj = None
                nombre_producto = descripcion[:255]

            unidad_base = unidad_medida

            producto = Producto.objects.filter(
                empresa=empresa,
                nombre=nombre_producto,
            ).first()

            if not producto:
                codigo_base = re.sub(r"[^A-Z0-9]", "", nombre_producto.upper())[:20]
                codigo = codigo_base or "PROD"
                sufijo = 1
                codigo_final = codigo
                while Producto.objects.filter(empresa=empresa, codigo=codigo_final).exists():
                    codigo_final = f"{codigo[:18]}{sufijo:02d}"
                    sufijo += 1

                producto = Producto.objects.create(
                    empresa=empresa,
                    nombre=nombre_producto,
                    codigo=codigo_final,
                    categoria=categoria,
                    activo=True,
                    precio=precio_unitario,
                    maneja_stock=True,
                    unidad_base=unidad_base,
                )

            # ── Guardar PMG en la variedad si fue informado ───────────────
            pmg_val = cd.get("pmg")
            if variedad_obj and pmg_val:
                variedad_obj.pmg = pmg_val
                variedad_obj.save(update_fields=["pmg"])

            # ── Crear ProductoSemilla si corresponde ───────────────────────
            if es_semilla and cultivo and variedad_obj:
                ProductoSemilla.objects.get_or_create(
                    producto=producto,
                    defaults={
                        "cultivo": cultivo,
                        "variedad": variedad_obj,
                    }
                )

        # ── Resolver presentación ──────────────────────────────────────────
        if pres_existente and not usar_nuevo:
            presentacion = pres_existente
        else:
            nombre_pres = (
                (cd.get("nueva_presentacion_nombre") or "").strip()
                or f"{unidad_detectada} {contenido_por_envase} {unidad_medida}"
            )
            unidad_contenido = unidad_medida

            presentacion, creado = PresentacionProducto.objects.get_or_create(
                producto=producto,
                nombre=nombre_pres,
                defaults={
                    "contenido":        contenido_por_envase,
                    "unidad_factura":   unidad_detectada,
                    "unidad_contenido": unidad_contenido,
                },
            )

        # ── Crear ítem y movimiento de stock ───────────────────────────────
        cantidad_base = cantidad_envases * contenido_por_envase

        factura_item = FacturaCompraItem.objects.create(
            factura=factura,
            producto=producto,
            presentacion=presentacion,
            cantidad_facturada=cantidad_envases,
            cantidad_base=cantidad_base,
            precio_unitario=precio_unitario,
            subtotal=subtotal,
        )

        MovimientoStock.objects.create(
            producto=producto,
            tipo=MovimientoStock.Tipo.ENTRADA,
            cantidad=cantidad_base,
            um=presentacion.unidad_contenido,
            factura_item=factura_item,
            fecha=timezone.now(),
            precio_unitario=precio_unitario,
            deposito_destino=deposito_destino,
        )

        total_factura += subtotal

    factura.total = total_factura
    factura.save(update_fields=["total"])

    request.session.pop("factura_temporal", None)
    request.session.pop("proveedor_seleccionado", None)

    messages.success(request, _("Factura %(numero)s guardada correctamente.") % {"numero": factura.numero})
    return redirect("vista_lista_facturas")

@login_required
def ajax_unidades_conversion(request):
    producto_id = request.GET.get("producto_id")
    if not producto_id:
        return JsonResponse({"ok": False, "error": "falta producto_id"}, status=400)
    try:
        producto = Producto.objects.get(id=producto_id)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False, "error": "producto no encontrado"}, status=404)

    unidad_base = producto.unidad_base
    conversiones = ConversionUM.objects.filter(um_destino=unidad_base).select_related("um_origen")

    lista = []
    for c in conversiones:
        lista.append({
            "id":          c.um_origen.id,
            "abreviatura": c.um_origen.abreviatura,
            "nombre":      c.um_origen.nombre,
            "factor":      str(c.factor),
        })

    return JsonResponse({
        "ok":                 True,
        "unidad_base_id":     unidad_base.id,
        "unidad_base_abrev":  unidad_base.abreviatura,
        "unidad_base_nombre": unidad_base.nombre,
        "categoria_id":       producto.categoria.id,
        "categoria_nombre":   producto.categoria.nombre,
        "unidades":           lista,
    })

@login_required
def ajax_transferir_stock(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    empresa = request.user.profile.empresa

    producto_id         = request.POST.get("producto_id")
    deposito_origen_id  = request.POST.get("deposito_origen_id")
    deposito_destino_id = request.POST.get("deposito_destino_id")
    cantidad_str        = request.POST.get("cantidad")
    unidad_id           = request.POST.get("unidad_id")
    fecha               = request.POST.get("fecha")
    destino             = request.POST.get("destino", "") or None
    observacion         = request.POST.get("observacion", "").strip()

    if not all([producto_id, deposito_origen_id, deposito_destino_id, cantidad_str, fecha]):
        return JsonResponse({"ok": False, "error": "Faltan datos obligatorios."}, status=400)

    if deposito_origen_id == deposito_destino_id:
        return JsonResponse({"ok": False, "error": "El depósito origen y destino no pueden ser el mismo."}, status=400)

    try:
        cantidad = Decimal(cantidad_str)
    except Exception:
        return JsonResponse({"ok": False, "error": "Cantidad inválida."}, status=400)

    if cantidad <= 0:
        return JsonResponse({"ok": False, "error": "La cantidad debe ser mayor a cero."}, status=400)

    try:
        producto = Producto.objects.get(id=producto_id, empresa=empresa)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Producto no encontrado."}, status=404)

    # convertir a unidad base si se eligió otra unidad
    unidad_ingresada = None
    if unidad_id:
        unidad_ingresada = Unidad.objects.filter(id=unidad_id).first()
    if not unidad_ingresada:
        unidad_ingresada = producto.unidad_base

    if unidad_ingresada != producto.unidad_base:
        try:
            cantidad = convertir_unidad(cantidad, unidad_ingresada, producto.unidad_base)
        except ValueError as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)

    try:
        origen = Deposito.objects.get(id=deposito_origen_id, empresa=empresa)
    except Deposito.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Depósito origen no encontrado."}, status=404)

    try:
        dep_destino = Deposito.objects.get(id=deposito_destino_id, empresa=empresa)
    except Deposito.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Depósito destino no encontrado."}, status=404)

    filtro_destino = {"destino": destino} if destino else {}
    entradas = MovimientoStock.objects.filter(
        producto=producto, tipo="ENTRADA", deposito_destino=origen, **filtro_destino
    )
    salidas = MovimientoStock.objects.filter(
        producto=producto, tipo="SALIDA", deposito_origen=origen, **filtro_destino
    )
    stock_origen = sum(m.cantidad for m in entradas) - sum(m.cantidad for m in salidas)

    if cantidad > stock_origen:
        return JsonResponse({
            "ok": False,
            "error": "Stock insuficiente en el depósito origen. Disponible: {} {}.".format(
                stock_origen, producto.unidad_base.abreviatura
            )
        }, status=400)

    with transaction.atomic():
        MovimientoStock.objects.create(
            producto=producto,
            tipo=MovimientoStock.Tipo.SALIDA,
            cantidad=cantidad,
            um=producto.unidad_base,
            fecha=fecha,
            precio_unitario=Decimal("0"),
            deposito_origen=origen,
            deposito_destino=None,
            destino=destino,
        )
        MovimientoStock.objects.create(
            producto=producto,
            tipo=MovimientoStock.Tipo.ENTRADA,
            cantidad=cantidad,
            um=producto.unidad_base,
            fecha=fecha,
            precio_unitario=Decimal("0"),
            deposito_origen=None,
            deposito_destino=dep_destino,
            destino=destino,
        )

    return JsonResponse({
        "ok": True,
        "message": "Transferencia realizada correctamente.",
    })

