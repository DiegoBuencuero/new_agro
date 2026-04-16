from datetime import datetime
import os, re
import base64
from django.core.files.base import ContentFile
from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch, Q
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from django.forms import formset_factory

import tempfile as tempfile

from .funciones_aux import parse_nfe_pdf, br_to_float, _buscar_candidatos, _score, _detectar_contenido_unidad

from .funciones_aux import ( registrar_actividad_aux, obtener_valores_costos, _detectar_contenido_unidad  )
from gestion_agro.forms import ( CampoForm, CampanaForm, CicloForm, CicloFiltroForm,
                                ActividadProductivaForm, ActividadInsumoForm, ActividadInsumoFormSet, CamposVistoriaForm, CamposCosechaForm,
                                StockFiltroForm, FacturaCompraForm, FacturaCompraItemFormSet)
from gestion_agro.models import ( Campo, Campana, CicloAgricola, FaseAgricola, SubTipoActividad,
                                ActividadProductiva, Producto, TipoActividad, TipoActividadCategoriaProducto,
                                ActividadInsumo, CategoriaProducto, MovimientoStock, 
                                FacturaCompra, Proveedor,  PresentacionProducto, FacturaCompraItem, Variedad
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

    return render(
        request,
        "vista_crear_campo.html",
        {
            "form": form,
            "campos": campos,
            "empresa": empresa,
        },
    )

@login_required
def vista_editar_campo(request, id_campo):
    campos = Campo.objects.filter(empresa = request.user.profile.empresa)
    try:
        campo = Campo.objects.get(id = id_campo)
    except:
        return redirect('vista_crear_campo')
    empresa = request.user.profile.empresa
    if campo.empresa ==empresa:
        if request.method == 'POST':
            form = CampoForm(request.POST, request.FILES, instance = campo)
            if form.is_valid():
                campo = form.save(commit=False)
                if request.POST.get('borrar') == '':
                    campo.delete()
                else:
                    campo.empresa = empresa
                    campo.save()
                return redirect('vista_crear_campo')
            else:
                messages.error(request, form.errors.as_data() )
        else:
            form = CampoForm(instance = campo)
        return render(request, 'vista_crear_campo.html', {'form': form, 'campos': campos, 'empresa': empresa, 'modificacion': 'S'})
    else:
        return redirect('vista_crear_campo')

@login_required
def vista_crear_campana(request):
    empresa = request.user.profile.empresa
    campanas = Campana.objects.filter(empresa=empresa)
    print(empresa)

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
def vista_editar_campana(request, id_campana):
    campanas = Campana.objects.filter(empresa = request.user.profile.empresa)
    try:
        camp = Campana.objects.get(id = id_campana)
    except:
        return redirect('vista_campana')
    empresa = request.user.profile.empresa
    if camp.empresa == empresa:
        if request.method == 'POST':
            form = CampanaForm(request.POST, instance = camp)
            if form.is_valid():
                campana = form.save(commit=False)
                if request.POST.get('borrar') == '':
                    campana.delete()
                else:
                    campana.save()
                return redirect('vista_campana')
        else:
            form = CampanaForm(instance = camp)
        return render(request, 'vista_campana.html', {'form': form, 'empresa': empresa, 'campanas':campanas, 'modificacion': 'S'})
    else:
        return redirect('vista_campana')
   
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
    empresa = request.user.profile.empresa

    if not empresa:
        messages.error(request, _("El usuario no tiene una empresa asociada."))
        return redirect("index")

    if request.method == "POST":
        form = CicloForm(request.POST, empresa=empresa)

        if form.is_valid():
            ciclo = form.save(commit=False)

            campo = ciclo.campo
            campana = ciclo.campana

            numero_lote = (
                CicloAgricola.objects
                .filter(campo=campo, campana=campana)
                .count() + 1
            )

            ciclo.nombre_lote = _("Lote-%(numero)s") % {
                "numero": numero_lote
            }
            ciclo.activa = True
            ciclo.save()

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
    }

    return render(request, "vista_crear_ciclo.html", context)

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
            Prefetch("insumos", queryset=insumos_qs)
        )
        .order_by("fecha", "id")
    )

    # solo leemos no calculamos nada
    costo_total_ciclo = sum(
        act.total or Decimal("0")
        for act in actividades
    )

    costo_ha_ciclo = Decimal("0")
    if ciclo.superficie_ha:
        costo_ha_ciclo = costo_total_ciclo / ciclo.superficie_ha

    fecha_fin_real = (
        fases.filter(estado="cerrado")
        .order_by("-fecha_fin")
        .values_list("fecha_fin", flat=True)
        .first()
    )

    precio_saco = getattr(ciclo, 'precio_saco', Decimal("0")) or Decimal("0")

    sacos_equilibrio_ha = Decimal("0")
    if precio_saco and costo_ha_ciclo:
        sacos_equilibrio_ha = costo_ha_ciclo / precio_saco

    rendimiento_esperado_sacos = getattr(ciclo, 'rendimiento_esperado_sacos', None)

    context = {
        "ciclo": ciclo,
        "fases": fases,
        "actividades": actividades,
        "costo_total_ciclo": costo_total_ciclo,
        "costo_ha_ciclo": costo_ha_ciclo,
        "precio_saco": precio_saco,
        "sacos_equilibrio_ha": sacos_equilibrio_ha,
        "rendimiento_esperado_sacos": rendimiento_esperado_sacos,
        "fecha_fin_real": fecha_fin_real,
    }

    return render(request, "vista_detalle_ciclo.html", context)

def vista_editar_ciclo():
    pass

@login_required
def ajax_subtipos_tipo_actividad(request):
    tipo_id = request.GET.get("tipo_id")

    if not tipo_id:
        return JsonResponse({
            "ok": False,
            "subtipos": []
        })

    subtipos = SubTipoActividad.objects.filter( tipo_actividad_id=tipo_id, activo=True).order_by("nombre")

    data = [
        {
            "id": subtipo.id,
            "nombre": subtipo.nombre
        }
        for subtipo in subtipos
    ]

    return JsonResponse({"ok": True, "subtipos": data })

@login_required
def vista_agregar_actividad(request, id_ciclo):
    empresa = request.user.profile.empresa

    ciclo = CicloAgricola.objects.filter(
        id=id_ciclo,
        campo__empresa=empresa,
    ).first()

    if not ciclo:
        messages.error(request, _("El ciclo no existe."))
        return redirect("vista_lista_ciclos")

    fase = (
        FaseAgricola.objects
        .filter(ciclo=ciclo)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    if request.method == "POST":
        actividad_form = ActividadProductivaForm(request.POST)

        insumo_formset = ActividadInsumoFormSet(
            request.POST,
            prefix="insumos",
            form_kwargs={"empresa": empresa},
            superficie=ciclo.superficie_ha, 
        )

        vistoria_form = CamposVistoriaForm(
            request.POST,
            request.FILES,
            prefix="vistoria",
        )

        cosecha_form = CamposCosechaForm(
            request.POST,
            prefix="cosecha",
        )

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

            if forms_validos:
                ok, resultado = registrar_actividad_aux(
                    ciclo=ciclo,
                    fase=fase,
                    empresa=empresa,
                    actividad_form=actividad_form,
                    insumo_formset=insumo_formset,
                    vistoria_form=vistoria_form,
                    cosecha_form=cosecha_form,
                )

                if ok:
                    if resultado["inicio_fase"]:
                        messages.success(request, _("Actividad registrada e inicio de fase generado."))
                    else:
                        messages.success(request, _("Actividad registrada correctamente."))

                    return redirect("vista_detalle_ciclo", id_ciclo=ciclo.id)

                messages.error(request, resultado)

        else:
            messages.error(request, _("Hay errores en el formulario."))

    else:
        actividad_form = ActividadProductivaForm(
            initial={"fecha": timezone.localdate()}
        )

        insumo_formset = ActividadInsumoFormSet(
            prefix="insumos",
            form_kwargs={"empresa": empresa},
            superficie=ciclo.superficie_ha,
        )

        vistoria_form = CamposVistoriaForm(prefix="vistoria")
        cosecha_form = CamposCosechaForm(prefix="cosecha")

    context = {
        "ciclo": ciclo,
        "actividad_form": actividad_form,
        "insumo_formset": insumo_formset,
        "vistoria_form": vistoria_form,
        "cosecha_form": cosecha_form,
    }

    return render(request, "vista_agregar_actividad.html", context)

@login_required
def ajax_productos_por_actividad(request):
    tipo_id = request.GET.get("tipo_id")
    subtipo_id = request.GET.get("subtipo_id")

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
        configuraciones_subtipo = configuraciones.filter(
            subtipo_actividad_id=subtipo_id
        )

        if configuraciones_subtipo.exists():
            configuraciones = configuraciones_subtipo
        else:
            configuraciones = configuraciones.filter(
                subtipo_actividad__isnull=True
            )
    else:
        configuraciones = configuraciones.filter(
            subtipo_actividad__isnull=True
        )

    categoria_ids = configuraciones.values_list(
        "categoria_producto_id",
        flat=True,
    )
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

    productos = productos.select_related("unidad_base").order_by("nombre")

    data = [
        {
            "id": producto.id,
            "nombre": producto.nombre,
            "unidad_id": producto.unidad_base_id,
            "unidad_abreviatura": (
                producto.unidad_base.abreviatura
                if producto.unidad_base else ""
            ),
        }
        for producto in productos
    ]

    return JsonResponse({
        "ok": True,
        "productos": data,
    })

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
def vista_lista_stock(request):
    form = StockFiltroForm(request.GET or None)

    productos = Producto.objects.select_related("categoria", "unidad_base").order_by("nombre")
    categorias = CategoriaProducto.objects.order_by("nombre")

    producto_txt = request.GET.get("producto")
    categoria = request.GET.get("categoria")
    fecha_desde = request.GET.get("fecha_entrada_desde")
    fecha_hasta = request.GET.get("fecha_entrada_hasta")

    if producto_txt:
        productos = productos.filter(nombre__icontains=producto_txt)

    if categoria:
        productos = productos.filter(categoria_id=categoria)

    lista_productos = []
    total_ingresado = 0
    total_consumido = 0
    total_restante = 0

    for producto in productos:

        movimientos = MovimientoStock.objects.filter(producto=producto)

        if fecha_desde:
            movimientos = movimientos.filter(fecha__gte=fecha_desde)

        if fecha_hasta:
            movimientos = movimientos.filter(fecha__lte=fecha_hasta)

        ingresado = 0
        consumido = 0

        for mov in movimientos:
            if mov.tipo == "ENTRADA":
                ingresado += mov.cantidad
            elif mov.tipo == "SALIDA":
                consumido += mov.cantidad

        ingresado = 0
        consumido = 0

        if not movimientos.exists():
            continue

        for mov in movimientos:
            if mov.tipo == "ENTRADA":
                ingresado += mov.cantidad
            elif mov.tipo == "SALIDA":
                consumido += mov.cantidad

        restante = ingresado - consumido

        total_ingresado += ingresado
        total_consumido += consumido
        total_restante += restante

        lista_productos.append({
            "obj": producto,
            "ingresado": ingresado,
            "consumido": consumido,
            "restante": restante,
        })

    context = {
        "form": form,                 
        "categorias": categorias,    
        "productos": lista_productos,
        "total_productos": len(lista_productos),
        "total_ingresado": total_ingresado,
        "total_consumido": total_consumido,
        "total_restante": total_restante,
    }

    return render(request, "vista_lista_stock.html", context)

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
    if request.method == "POST":
        empresa = request.user.profile.empresa
        
        try:
            factura = FacturaCompra.objects.create(
                empresa=empresa,
                proveedor_id=request.POST.get("proveedor"),
                numero=request.POST.get("numero"),
                fecha=request.POST.get("fecha"),
                total=request.POST.get("total"),
                archivo_pdf=request.FILES.get("archivo_pdf"),  # <-- salva o PDF
            )
            messages.success(request, "Factura cargada correctamente.")
            return redirect("vista_lista_facturas")

        except Exception as e:
            messages.error(request, f"Error al guardar: {e}")

    proveedores = Proveedor.objects.filter(empresa=request.user.profile.empresa)
    return render(request, "tem_facturas/vista_cargar_factura.html", {
        "proveedores": proveedores
    })

@login_required
def vista_cargar_factura_manual(request):
    return render(request, "tem_facturas/vista_cargar_factura_manual.html")

@login_required
def vista_procesar_pdf_factura(request):
    if request.method != "POST":
        return redirect("vista_cargar_factura")

    pdf_file = request.FILES.get("pdf_file")
    if not pdf_file:
        messages.error(request, _("No se ha seleccionado ningún archivo PDF."))
        return redirect("vista_cargar_factura")

    # Leer contenido antes de escribir el temp
    pdf_content = pdf_file.read()
    pdf_file.seek(0)

    pdf_content = pdf_file.read()
    pdf_file.seek(0)

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
            "pdf_base64": base64.b64encode(pdf_content).decode("utf-8"),  # ← dentro do dict
            "pdf_nombre": pdf_file.name,                                   # ← dentro do dict
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

    proveedor_obj, _ = Proveedor.objects.get_or_create(
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
                PresentacionProducto.objects.filter(producto_id=prod).order_by("nombre")
            )

        pres_match = next(
            (p for p in presentaciones if p.unidad_factura.upper() == unid_factura.upper()),
            None,
    )

        initial_data.append({
            "descripcion":               desc,
            "unidad_detectada":          unid_factura,
            "cantidad":                  cant,
            "precio_unitario":           p_u,
            "subtotal":                  cant * p_u,
            "contenido_por_envase":      contenido,
            "unidad_medida":             unidad,
            "nueva_presentacion_nombre": pres_nombre,
            "producto_existente":        mejor_producto.id if mejor_producto else None,
            "presentacion_existente":    pres_match.id if pres_match else None,
            "nueva_presentacion_nombre": f"Envase {contenido} {unidad}",
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

    # Pre-cargar presentaciones en el form según el candidato principal
    for i, form in enumerate(formset):
        prod = initial_data[i].get("producto_existente")
        if prod:
            form.fields["presentacion_existente"].queryset = (
                PresentacionProducto.objects.filter(producto_id=prod).order_by("nombre")
            )

    context = {
        "cabecera_form":   cabecera_form,
        "formset":         formset,
        "items_con_match": list(zip(formset, match_info)),
        "items":           items,
        "nombre_archivo":  factura_temp["nombre_archivo"],
        "datos_factura":   datos_factura,
        "proveedor":       proveedor_obj,
        "empresa_usuario": empresa,
        "categorias":      CategoriaProducto.objects.all().order_by("nombre"),
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
        return render(request, "tem_facturas/vista_revisar_factura.html", {
            "cabecera_form":   cabecera_form,
            "formset":         formset,
            "items_con_match": [
                (f, {"score": 0, "label": "ninguno", "candidatos": [], "presentaciones": []})
                for f in formset
            ],
            "items":          factura_temp["items"],
            "nombre_archivo": factura_temp["nombre_archivo"],
            "datos_factura":  factura_temp["datos_factura"],
            "proveedor":      proveedor,
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
            _(f"La factura {numero_factura} ya fue ingresada para este proveedor.")
        )
        request.session.pop("factura_temporal", None)
        request.session.pop("proveedor_seleccionado", None)
        return redirect("vista_lista_facturas")

    # ── Unidad helper ──────────────────────────────────────────────────────
    from agro.models import Unidad

    def resolver_unidad(nombre):
        return (
            Unidad.objects.filter(nombre__iexact=nombre).first()
            or Unidad.objects.filter(abreviatura__iexact=nombre).first()
            or Unidad.objects.first()
        )

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
    items_raw     = factura_temp["items"]

    for i, form in enumerate(formset):
        cd = form.cleaned_data
        if not cd:
            continue

        usar_nuevo       = cd.get("crear_nuevo_producto")
        prod_existente   = cd.get("producto_existente")
        pres_existente   = cd.get("presentacion_existente")

        descripcion      = (cd.get("descripcion") or "").strip()
        unidad_detectada = (cd.get("unidad_detectada") or "UN").strip()
        categoria        = cd.get("categoria")
        cultivo          = cd.get("cultivo")
        variedad         = cd.get("variedad")
        variedad_manual  = (cd.get("variedad_manual") or "").strip()

        cantidad_envases     = cd["cantidad"]
        contenido_por_envase = cd["contenido_por_envase"]
        unidad_medida        = cd["unidad_medida"]
        precio_unitario      = cd["precio_unitario"]
        subtotal             = cd.get("subtotal") or (cantidad_envases * precio_unitario)

        # ── Resolver producto ──────────────────────────────────────────────
        if prod_existente and not usar_nuevo:
            producto = prod_existente
        else:
            if categoria and "semilla" in categoria.nombre.lower():
                if variedad_manual and cultivo:
                    variedad, creada = Variedad.objects.get_or_create(
                        cultivo=cultivo, nombre=variedad_manual
                    )
                nombre_producto = f"{descripcion[:180]} - {cultivo.nombre} {variedad.nombre}"
            else:
                nombre_producto = descripcion[:255]

            unidad_base = resolver_unidad(unidad_medida)

            producto = Producto.objects.filter(
                empresa=empresa,
                nombre=nombre_producto,
            ).first()

            if not producto:
                import re
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

        # ── Resolver presentación ──────────────────────────────────────────
        if pres_existente and not usar_nuevo:
            presentacion = pres_existente
        else:
            nombre_pres = (
                (cd.get("nueva_presentacion_nombre") or "").strip()
                or f"{unidad_detectada} {contenido_por_envase} {unidad_medida}"
            )
            unidad_contenido = resolver_unidad(unidad_medida)

            presentacion, pres_creada = PresentacionProducto.objects.get_or_create(
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
        )

        total_factura += subtotal

    factura.total = total_factura
    factura.save(update_fields=["total"])

    request.session.pop("factura_temporal", None)
    request.session.pop("proveedor_seleccionado", None)

    messages.success(request, _(f"Factura {factura.numero} guardada correctamente."))
    return redirect("vista_lista_facturas")