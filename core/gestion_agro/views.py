from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.db.models import Prefetch
from .funciones_aux import ( registrar_actividad_aux, obtener_valores_costos  )
from gestion_agro.forms import ( CampoForm, CampanaForm, CicloForm, CicloFiltroForm,
                                ActividadProductivaForm, ActividadInsumoForm, ActividadInsumoFormSet, CamposVistoriaForm, CamposCosechaForm, StockFiltroForm)
from gestion_agro.models import ( Campo, Campana, CicloAgricola, FaseAgricola, SubTipoActividad,
                                ActividadProductiva, Producto, TipoActividad, TipoActividadCategoriaProducto,
                                CamposVistoria, CamposCosecha, ActividadInsumo, Producto, CategoriaProducto, MovimientoStock)


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

    costo_total_ciclo = 0

    for act in actividades:
        total_mo = 0
        total_mq = 0
        total_insumos = 0

        if act.cantidad_hombre and act.valor_hombre:
            total_mo = act.cantidad_hombre * act.valor_hombre

        if act.cantidad_h_maq and act.valor_h_maq:
            total_mq = act.cantidad_h_maq * act.valor_h_maq

        for insumo in act.insumos.all():
            costo_insumo = 0

            if insumo.dosis and insumo.producto and insumo.producto.precio:
                costo_insumo = insumo.dosis * insumo.producto.precio

            insumo.costo_total = costo_insumo
            total_insumos += costo_insumo

        act.total_mo = total_mo
        act.total_mq = total_mq
        act.total_insumos = total_insumos
        act.total_actividad = total_mo + total_mq + total_insumos

        # si en tu template vienes usando act.total
        act.total = act.total_actividad

        costo_total_ciclo += act.total_actividad

    costo_ha_ciclo = 0
    if ciclo.superficie_ha:
        costo_ha_ciclo = costo_total_ciclo / ciclo.superficie_ha

    context = {
        "ciclo": ciclo,
        "fases": fases,
        "actividades": actividades,
        "costo_total_ciclo": costo_total_ciclo,
        "costo_ha_ciclo": costo_ha_ciclo,
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
                messages.error(request, _("Hay errores en los datos de la actividad."))

        else:
            messages.error(request, _("Hay errores en el formulario."))

    else:
        actividad_form = ActividadProductivaForm(
            initial={"fecha": timezone.localdate()}
        )

        insumo_formset = ActividadInsumoFormSet(
            prefix="insumos",
            form_kwargs={"empresa": empresa},
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

from django.shortcuts import get_object_or_404, render

from .forms import StockFiltroForm
from .models import Producto, MovimientoStock


def vista_lista_stock(request):
    productos = (
        Producto.objects
        .select_related("categoria", "unidad_base")
        .order_by("nombre")
    )

    form = StockFiltroForm(request.GET or None)

    lista_productos = []
    total_ingresado = 0
    total_consumido = 0
    total_restante = 0

    for producto in productos:
        movimientos = MovimientoStock.objects.filter(producto=producto)

        ingresado = 0
        consumido = 0

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

    producto_seleccionado = None
    producto_id = request.GET.get("producto_id")

    if producto_id:
        producto_seleccionado = get_object_or_404(productos, pk=producto_id)

    context = {
        "form": form,
        "productos": lista_productos,
        "producto_seleccionado": producto_seleccionado,
        "total_productos": len(lista_productos),
        "total_ingresado": total_ingresado,
        "total_consumido": total_consumido,
        "total_restante": total_restante,
    }

    return render(request, "vista_lista_stock.html", context)