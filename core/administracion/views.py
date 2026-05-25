from decimal import Decimal, InvalidOperation
from django.shortcuts import render
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from decimal import Decimal as _Decimal
from django.contrib import messages
from django.shortcuts import redirect
from gestion_agro.models import FacturaCompra, Proveedor, Producto, MovimientoStock, Cliente
from .models import Pago, AplicacionPago, FacturaVenta, FacturaVentaItem, Recibo, AplicacionRecibo
from .forms import FiltroFacturasForm, AplicacionPagoForm, FacturaVentaForm, FacturaVentaItemForm, AplicacionReciboForm, FacturaVentaManualForm, FacturaVentaManualItemFormSet


@login_required
def vista_registrar_venta(request):
    empresa  = request.user.profile.empresa
    producto_id = request.GET.get("producto_id") or request.POST.get("producto_id")
    destino     = request.GET.get("destino")     or request.POST.get("destino")
    deposito_id = request.GET.get("deposito_id") or request.POST.get("deposito_id")

    try:
        producto = Producto.objects.get(id=producto_id, empresa=empresa)
    except Producto.DoesNotExist:
        messages.error(request, _("Producto no encontrado."))
        return redirect("vista_lista_stock")

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": _("Método no permitido.")}, status=405)

    factura_form = FacturaVentaForm(empresa, request.POST)
    item_form    = FacturaVentaItemForm(empresa, producto, request.POST)

    # — validación de formularios —
    if not factura_form.is_valid() or not item_form.is_valid():
        errores = []
        for f in [factura_form, item_form]:
            for field, errs in f.errors.items():
                lbl = f.fields[field].label if field in f.fields else field
                for e in errs:
                    errores.append(f"{lbl}: {e}")
        return JsonResponse({"ok": False, "error": " | ".join(errores)}, status=400)

    cantidad        = item_form.cleaned_data["cantidad"]
    deposito_origen = item_form.cleaned_data.get("deposito_origen")
    um              = item_form.cleaned_data.get("um") or producto.unidad_base

    # — conversión de unidad —
    from gestion_agro.funciones_aux import convertir_unidad
    try:
        cantidad_base = convertir_unidad(cantidad, um, producto.unidad_base)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    # — stock disponible para ese producto + destino + depósito —
    filtro_dep = {"deposito_destino": deposito_origen} if deposito_origen else {}
    filtro_dst = {"destino": destino} if destino else {}
    entradas = MovimientoStock.objects.filter(producto=producto, tipo="ENTRADA", **filtro_dep, **filtro_dst)
    ventas   = MovimientoStock.objects.filter(producto=producto, tipo="VENTA",   deposito_origen=deposito_origen, **filtro_dst)
    stock    = sum(m.cantidad for m in entradas) - sum(m.cantidad for m in ventas)

    if cantidad_base > stock:
        return JsonResponse({
            "ok": False,
            "error": str(_("Stock insuficiente. Disponible: %(s)s %(u)s.") % {
                "s": round(stock, 3), "u": producto.unidad_base,
            }),
        }, status=400)

    # — guardar —
    with transaction.atomic():
        factura = factura_form.save(commit=False)
        factura.empresa = empresa
        factura.usuario = request.user
        factura.save()

        item = item_form.save(commit=False)
        item.factura  = factura
        item.producto = producto
        item.destino  = destino
        item.save()

        MovimientoStock.objects.create(
            producto           = producto,
            tipo               = MovimientoStock.Tipo.VENTA,
            cantidad           = cantidad_base,
            um                 = producto.unidad_base,
            fecha              = factura.fecha,
            deposito_origen    = deposito_origen,
            deposito_destino   = None,
            destino            = destino,
            precio_unitario    = item.precio_unitario,
            factura_venta_item = item,
        )

    return JsonResponse({"ok": True})


@login_required
def ajax_registrar_cobro(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    empresa      = request.user.profile.empresa
    factura_id   = request.POST.get("factura_id")
    monto_raw    = request.POST.get("monto")
    observaciones = request.POST.get("observaciones", "").strip()

    try:
        factura = FacturaVenta.objects.get(id=factura_id, empresa=empresa)
    except FacturaVenta.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Factura no encontrada."}, status=404)

    form = AplicacionReciboForm(empresa=empresa, data={"factura": factura_id, "monto_aplicado": monto_raw})
    if not form.is_valid():
        errores = [e for errs in form.errors.values() for e in errs]
        return JsonResponse({"ok": False, "error": " | ".join(errores)}, status=400)

    with transaction.atomic():
        recibo = Recibo.objects.create(
            empresa=empresa,
            cliente=factura.cliente,
            observaciones=observaciones,
        )
        aplicacion = form.save(commit=False)
        aplicacion.recibo = recibo
        aplicacion.save()

    total   = sum(i.cantidad * i.precio_unitario for i in factura.items.all())
    cobrado = factura.aplicaciones.aggregate(t=Coalesce(Sum("monto_aplicado"), _Decimal("0")))["t"]
    saldo   = total - cobrado

    return JsonResponse({
        "ok":     True,
        "saldo":  float(saldo),
        "estado": "cobrada" if saldo <= 0 else "pendiente",
    })


@login_required
def vista_lista_ventas(request):
    empresa = request.user.profile.empresa

    qs = (
        FacturaVenta.objects
        .filter(empresa=empresa)
        .prefetch_related("items__producto", "items__deposito_origen", "aplicaciones")
        .select_related("cliente")
        .order_by("-fecha")
    )

    # filtros GET
    cliente_id  = request.GET.get("cliente")
    fecha_desde = request.GET.get("fecha_desde")
    fecha_hasta = request.GET.get("fecha_hasta")

    from gestion_agro.models import Cliente
    clientes = Cliente.objects.filter(empresa=empresa).order_by("razon_social")

    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)
    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)

    facturas = []
    for f in qs:
        total = sum(i.cantidad * i.precio_unitario for i in f.items.all())
        cobrado = f.aplicaciones.aggregate(t=Coalesce(Sum("monto_aplicado"), _Decimal("0")))["t"]
        saldo = total - cobrado
        facturas.append({
            "obj":     f,
            "total":   total,
            "cobrado": cobrado,
            "saldo":   saldo,
            "estado":  "cobrada" if saldo <= 0 else "pendiente",
        })

    return render(request, "tem_administracion/lista_ventas.html", {
        "facturas":    facturas,
        "clientes":    clientes,
        "cliente_id":  cliente_id or "",
        "fecha_desde": fecha_desde or "",
        "fecha_hasta": fecha_hasta or "",
    })


@login_required
def vista_gestion_facturas(request):
    empresa = request.user.profile.empresa
    form = FiltroFacturasForm(empresa)
    return render(request, "tem_administracion/gestion_facturas.html", {"form": form})

@login_required
def ajax_indicadores_proveedor(request):

    if request.method != "POST":
        return JsonResponse(
            {"error": "method not allowed"},
            status=405
        )

    empresa = request.user.profile.empresa
    proveedor_id = request.POST.get("proveedor_id" )
    facturas = FacturaCompra.objects.filter( empresa=empresa )

    # Si eligieron proveedor, filtrar
    if proveedor_id:
        facturas = facturas.filter( proveedor_id=proveedor_id  )

    facturas = facturas.annotate( pagado=Sum("aplicaciones__monto_aplicado" ))

    hoy = timezone.now().date()
    total_facturas = facturas.count()
    saldo_pendiente = Decimal("0")

    for factura in facturas:

        pagado = factura.pagado or Decimal("0")
        deuda = factura.total - pagado
        if deuda > 0:
            saldo_pendiente += deuda

    vencidas = 0

    for factura in facturas:

        pagado = factura.pagado or Decimal("0")
        deuda = factura.total - pagado

        if deuda > 0:

            if factura.fecha_vencimiento:

                # Ya venció
                if factura.fecha_vencimiento < hoy:
                    vencidas += 1

    prox_venc = None

    facturas_ordenadas = facturas.order_by("fecha_vencimiento")

    for factura in facturas_ordenadas:
        pagado = factura.pagado or Decimal("0")
        deuda = factura.total - pagado

        if deuda > 0:
            if factura.fecha_vencimiento:
                if factura.fecha_vencimiento >= hoy:
                    prox_venc = factura.fecha_vencimiento
                    break

    return JsonResponse({
        "total_facturas": total_facturas,
        "saldo_pendiente": str(
            saldo_pendiente
        ),
        "vencidas": vencidas,
        "prox_vencimiento":
            prox_venc.strftime("%d/%m/%Y")
            if prox_venc
            else "—",
    })


@login_required
def ajax_buscar_facturas(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    empresa = request.user.profile.empresa
    form = FiltroFacturasForm(empresa, request.POST)

    if not form.is_valid():
        return JsonResponse({"error": str(form.errors)}, status=400)

    qs = (
        FacturaCompra.objects
        .filter(empresa=empresa)
        .annotate(pagado=Coalesce(Sum("aplicaciones__monto_aplicado"), Decimal("0")))
        .select_related("proveedor")
        .order_by("-fecha")
    )

    proveedor = form.cleaned_data.get("proveedor")
    fecha_desde = form.cleaned_data.get("fecha_desde")
    fecha_hasta = form.cleaned_data.get("fecha_hasta")

    if proveedor:
        qs = qs.filter(proveedor=proveedor)
    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)

    hoy = timezone.now().date()
    facturas = []
    for f in qs:
        saldo = f.total - f.pagado
        if saldo <= 0:
            estado = "pagada"
        elif f.fecha_vencimiento and f.fecha_vencimiento < hoy:
            estado = "vencida"
        else:
            estado = "pendiente"

        aplicaciones = []

        lista_aplicaciones = (f.aplicaciones.select_related("pago").order_by("pago__fecha"))

        for aplicacion in lista_aplicaciones:
            dato = {
                "fecha": aplicacion.pago.fecha.strftime(
                    "%d/%m/%Y %H:%M"
                ),
                "monto_aplicado": aplicacion.monto_aplicado,
                "pago_id": aplicacion.pago_id,
            }

            aplicaciones.append(
                dato
            )

        facturas.append({
            "id":               f.id,
            "numero":           f.numero,
            "proveedor":        str(f.proveedor),
            "fecha":            f.fecha.strftime("%d/%m/%Y"),
            "fecha_vencimiento":f.fecha_vencimiento.strftime("%d/%m/%Y") if f.fecha_vencimiento else "–",
            "total":            f.total,
            "pagado":           f.pagado,
            "saldo":            saldo,
            "estado":           estado,
            "aplicaciones":     aplicaciones,
        })

    proveedor_id = proveedor.id if proveedor else ""
    html = render_to_string(
        "tem_administracion/_tabla_facturas.html",
        {"facturas": facturas, "proveedor_id": proveedor_id},
        request=request,
    )
    return JsonResponse({"html": html})

@login_required
def ajax_registrar_pago(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    empresa = request.user.profile.empresa
    proveedor_id = request.POST.get("proveedor_id")
    factura_ids = request.POST.getlist("factura_id[]")
    montos_raw = request.POST.getlist("monto[]")

    if not proveedor_id or not factura_ids:
        return JsonResponse({"ok": False, "error": str(_("Seleccione al menos una factura"))})

    try:
        proveedor = Proveedor.objects.get(id=proveedor_id, empresa=empresa)
    except Proveedor.DoesNotExist:
        return JsonResponse({"ok": False, "error": str(_("Proveedor inválido"))})

    # Validar cada ítem con AplicacionPagoForm — la lógica de saldo vive en el form
    forms_validos = []
    errores = []

    for factura_id, monto_raw in zip(factura_ids, montos_raw):
        form = AplicacionPagoForm(empresa=empresa, data={"factura": factura_id, "monto_aplicado": monto_raw})
        if form.is_valid():
            forms_validos.append(form)
        else:
            for field_errors in form.errors.values():
                errores.extend(field_errors)

    if errores:
        return JsonResponse({"ok": False, "error": "\n".join(errores)})

    if not forms_validos:
        return JsonResponse({"ok": False, "error": str(_("No hay pagos válidos para registrar"))})

    with transaction.atomic():
        pago = Pago.objects.create(empresa=empresa, proveedor=proveedor)
        for form in forms_validos:
            aplicacion = form.save(commit=False)
            aplicacion.pago = pago
            aplicacion.save()

    return JsonResponse({
        "ok": True,
        "pago_id": pago.id,
        "message": str(_("Pago registrado correctamente")),
    })

@login_required
def ajax_buscar_pagos(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    empresa = request.user.profile.empresa
    form = FiltroFacturasForm(empresa, request.POST)

    if not form.is_valid():
        return JsonResponse({"error": str(form.errors)}, status=400)

    qs = (
        Pago.objects
        .filter(empresa=empresa)
        .prefetch_related("aplicaciones__factura")
        .select_related("proveedor")
        .order_by("-fecha")
    )

    proveedor = form.cleaned_data.get("proveedor")
    fecha_desde = form.cleaned_data.get("fecha_desde")
    fecha_hasta = form.cleaned_data.get("fecha_hasta")

    if proveedor:
        qs = qs.filter(proveedor=proveedor)
    if fecha_desde:
        qs = qs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__date__lte=fecha_hasta)

    html = render_to_string(
        "tem_administracion/_tabla_pagos.html",
        {"pagos": list(qs)},
        request=request,
    )
    return JsonResponse({"html": html})

@login_required
def ajax_detalle_pago(request, pago_id):
    empresa = request.user.profile.empresa
    pago = get_object_or_404(
        Pago.objects.prefetch_related("aplicaciones__factura").select_related("proveedor"),
        id=pago_id,
        empresa=empresa,
    )
    html = render_to_string(
        "tem_administracion/_comprobante_pago.html",
        {"pago": pago},
        request=request,
    )
    return JsonResponse({"html": html})


@login_required
def ajax_info_producto_venta(request):
    producto_id = request.GET.get("producto_id")
    if not producto_id:
        return JsonResponse({"ok": False}, status=400)
    try:
        producto = Producto.objects.select_related(
            "categoria", "unidad_base",
            "datos_semilla__cultivo", "datos_semilla__variedad",
        ).get(id=producto_id, empresa=request.user.profile.empresa, producto_final=True)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False}, status=404)

    from django.db.models import Sum
    from django.db.models.functions import Coalesce
    from decimal import Decimal as D

    destinos_disponibles = []
    for valor, etiqueta in [("M", str(_("Semilla (M)"))), ("C", str(_("Consumo (C)")))]:
        entradas = (
            MovimientoStock.objects
            .filter(producto=producto, tipo="ENTRADA", destino=valor)
            .aggregate(t=Coalesce(Sum("cantidad"), D("0")))["t"]
        )
        ventas = (
            MovimientoStock.objects
            .filter(producto=producto, tipo="VENTA", destino=valor)
            .aggregate(t=Coalesce(Sum("cantidad"), D("0")))["t"]
        )
        stock = entradas - ventas
        if stock > 0:
            destinos_disponibles.append({
                "value": valor,
                "label": etiqueta,
                "stock": float(round(stock, 3)),
                "um":    producto.unidad_base.abreviatura,
            })

    return JsonResponse({
        "ok":      True,
        "destinos": destinos_disponibles,
        "unidad_base": producto.unidad_base.abreviatura,
    })


@login_required
def ajax_depositos_producto_destino(request):
    producto_id = request.GET.get("producto_id")
    destino     = request.GET.get("destino")
    if not producto_id or not destino:
        return JsonResponse({"ok": False}, status=400)

    empresa = request.user.profile.empresa
    try:
        producto = Producto.objects.get(id=producto_id, empresa=empresa, producto_final=True)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False}, status=404)

    from django.db.models import Sum
    from django.db.models.functions import Coalesce
    from decimal import Decimal as D
    from gestion_agro.models import Deposito

    depositos_ids_entradas = (
        MovimientoStock.objects
        .filter(producto=producto, tipo="ENTRADA", destino=destino, deposito_destino__isnull=False)
        .values_list("deposito_destino_id", flat=True)
        .distinct()
    )

    resultado = []
    for dep in Deposito.objects.filter(id__in=depositos_ids_entradas).order_by("nombre"):
        entradas = (
            MovimientoStock.objects
            .filter(producto=producto, tipo="ENTRADA", destino=destino, deposito_destino=dep)
            .aggregate(t=Coalesce(Sum("cantidad"), D("0")))["t"]
        )
        ventas = (
            MovimientoStock.objects
            .filter(producto=producto, tipo="VENTA", destino=destino, deposito_origen=dep)
            .aggregate(t=Coalesce(Sum("cantidad"), D("0")))["t"]
        )
        stock = entradas - ventas
        if stock > 0:
            resultado.append({
                "id":    dep.id,
                "nombre": dep.nombre,
                "stock": float(round(stock, 3)),
                "um":    producto.unidad_base.abreviatura,
            })

    return JsonResponse({"ok": True, "depositos": resultado})


def _productos_venta(empresa):
    qs = (
        Producto.objects
        .filter(empresa=empresa, activo=True, producto_final=True)
        .select_related("categoria", "datos_semilla__cultivo", "datos_semilla__variedad")
        .order_by("nombre")
    )
    resultado = []
    for p in qs:
        try:
            ds = p.datos_semilla
            label = f"{ds.cultivo.nombre} {ds.variedad.nombre}"
        except Exception:
            label = p.nombre
        resultado.append({"id": p.id, "label": label})
    return resultado


@login_required
def vista_cargar_factura_venta_manual(request):
    empresa = request.user.profile.empresa
    from gestion_agro.models import Deposito

    TEMPLATE = "tem_administracion/cargar_factura_venta.html"

    def _context(factura_form, formset):
        return {
            "factura_form": factura_form,
            "formset":      formset,
            "productos":    _productos_venta(empresa),
            "depositos":    Deposito.objects.filter(empresa=empresa).order_by("nombre"),
        }

    def _make_formset(data=None):
        return FacturaVentaManualItemFormSet(
            data, prefix="items", form_kwargs={"empresa": empresa}
        )

    if request.method == "POST":
        factura_form = FacturaVentaManualForm(empresa, request.POST)
        formset = _make_formset(request.POST)

        if "agregar_item" in request.POST:
            data = request.POST.copy()
            data["items-TOTAL_FORMS"] = int(data.get("items-TOTAL_FORMS", 0)) + 1
            return render(request, TEMPLATE, _context(
                FacturaVentaManualForm(empresa, request.POST),
                _make_formset(data),
            ))

        if "ok" in request.POST:
            if factura_form.is_valid() and formset.is_valid():
                items_validos = [f.cleaned_data for f in formset if f.cleaned_data]

                errores_stock = []
                for i, cd in enumerate(items_validos):
                    producto      = cd["producto"]
                    cantidad      = cd["cantidad"]
                    destino       = cd.get("destino") or None
                    deposito_orig = cd.get("deposito_origen")

                    qs_entradas = MovimientoStock.objects.filter(
                        producto=producto, tipo="ENTRADA", destino=destino
                    )
                    qs_ventas = MovimientoStock.objects.filter(
                        producto=producto, tipo="VENTA", destino=destino
                    )
                    if deposito_orig:
                        qs_entradas = qs_entradas.filter(deposito_destino=deposito_orig)
                        qs_ventas   = qs_ventas.filter(deposito_origen=deposito_orig)

                    from django.db.models import Sum as _Sum
                    from django.db.models.functions import Coalesce as _Coalesce
                    from decimal import Decimal as _D
                    total_entradas = qs_entradas.aggregate(t=_Coalesce(_Sum("cantidad"), _D("0")))["t"]
                    total_ventas   = qs_ventas.aggregate(t=_Coalesce(_Sum("cantidad"), _D("0")))["t"]
                    stock_disp     = total_entradas - total_ventas

                    if cantidad > stock_disp:
                        errores_stock.append(
                            _("Ítem %(n)s (%(p)s): stock insuficiente. Disponible: %(s)s %(u)s.") % {
                                "n": i + 1,
                                "p": producto.nombre,
                                "s": round(stock_disp, 3),
                                "u": producto.unidad_base,
                            }
                        )

                if errores_stock:
                    for err in errores_stock:
                        messages.error(request, err)
                elif items_validos:
                    with transaction.atomic():
                        factura = factura_form.save(commit=False)
                        factura.empresa = empresa
                        factura.usuario = request.user
                        factura.save()

                        for cd in items_validos:
                            producto      = cd["producto"]
                            destino       = cd.get("destino") or None
                            deposito_orig = cd.get("deposito_origen")

                            item = FacturaVentaItem.objects.create(
                                factura         = factura,
                                producto        = producto,
                                cantidad        = cd["cantidad"],
                                precio_unitario = cd["precio_unitario"],
                                deposito_origen = deposito_orig,
                                destino         = destino,
                                um              = producto.unidad_base,
                            )
                            MovimientoStock.objects.create(
                                producto           = producto,
                                tipo               = MovimientoStock.Tipo.VENTA,
                                cantidad           = cd["cantidad"],
                                um                 = producto.unidad_base,
                                fecha              = factura.fecha,
                                deposito_origen    = deposito_orig,
                                deposito_destino   = None,
                                destino            = destino,
                                precio_unitario    = cd["precio_unitario"],
                                factura_venta_item = item,
                            )

                    messages.success(request, _("Factura de venta cargada correctamente."))
                    return redirect("vista_lista_ventas")
            else:
                messages.error(request, _("Revisá los errores del formulario."))
    else:
        factura_form = FacturaVentaManualForm(empresa)
        formset = _make_formset()

    return render(request, TEMPLATE, _context(factura_form, formset))


@login_required
def vista_cuenta_corriente_proveedor(request):
    from datetime import date
    empresa = request.user.profile.empresa
    hoy = date.today()

    proveedores = Proveedor.objects.filter(empresa=empresa).order_by("razon_social")

    proveedor_id = request.GET.get("proveedor") or ""
    fecha_desde  = request.GET.get("fecha_desde") or ""
    fecha_hasta  = request.GET.get("fecha_hasta") or ""
    estado_filtro = request.GET.get("estado") or ""

    qs = (
        FacturaCompra.objects
        .filter(empresa=empresa)
        .annotate(pagado=Coalesce(Sum("aplicaciones__monto_aplicado"), Decimal("0")))
        .select_related("proveedor")
        .prefetch_related("aplicaciones__pago")
        .order_by("fecha")
    )
    if proveedor_id:
        qs = qs.filter(proveedor_id=proveedor_id)
    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)

    filas = []
    total_deuda = Decimal("0")
    cant_vencidas = 0
    prox_vencimiento = None

    for f in qs:
        saldo = f.total - f.pagado
        if saldo <= 0:
            estado = "pagada"
        elif f.fecha_vencimiento and f.fecha_vencimiento < hoy:
            estado = "vencida"
        else:
            estado = "pendiente"

        if estado_filtro and estado != estado_filtro:
            continue

        if saldo > 0:
            total_deuda += saldo
        if estado == "vencida":
            cant_vencidas += 1
        if estado == "pendiente" and f.fecha_vencimiento:
            if prox_vencimiento is None or f.fecha_vencimiento < prox_vencimiento:
                prox_vencimiento = f.fecha_vencimiento

        comprobantes = [
            {
                "numero": ap.pago_id,
                "fecha":  ap.pago.fecha,
                "monto":  ap.monto_aplicado,
            }
            for ap in f.aplicaciones.all()
        ]

        filas.append({
            "obj":          f,
            "total":        f.total,
            "pagado":       f.pagado,
            "saldo":        saldo,
            "estado":       estado,
            "comprobantes": comprobantes,
        })

    return render(request, "tem_administracion/cuenta_corriente_proveedor.html", {
        "filas":            filas,
        "proveedores":      proveedores,
        "proveedor_id":     proveedor_id,
        "fecha_desde":      fecha_desde,
        "fecha_hasta":      fecha_hasta,
        "estado_filtro":    estado_filtro,
        "total_deuda":      total_deuda,
        "cant_vencidas":    cant_vencidas,
        "prox_vencimiento": prox_vencimiento,
    })


@login_required
def vista_cuenta_corriente_cliente(request):
    from datetime import date
    empresa = request.user.profile.empresa
    hoy = date.today()

    clientes = Cliente.objects.filter(empresa=empresa).order_by("razon_social")

    cliente_id    = request.GET.get("cliente") or ""
    fecha_desde   = request.GET.get("fecha_desde") or ""
    fecha_hasta   = request.GET.get("fecha_hasta") or ""
    estado_filtro = request.GET.get("estado") or ""

    qs = (
        FacturaVenta.objects
        .filter(empresa=empresa)
        .annotate(cobrado=Coalesce(Sum("aplicaciones__monto_aplicado"), Decimal("0")))
        .select_related("cliente")
        .prefetch_related("aplicaciones__recibo", "items")
        .order_by("fecha")
    )
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)
    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)

    filas = []
    total_por_cobrar = Decimal("0")
    cant_vencidas = 0
    prox_vencimiento = None

    for f in qs:
        total_fv = sum(i.cantidad * i.precio_unitario for i in f.items.all())
        saldo = total_fv - f.cobrado
        if saldo <= 0:
            estado = "cobrada"
        elif f.fecha_vencimiento and f.fecha_vencimiento < hoy:
            estado = "vencida"
        else:
            estado = "pendiente"

        if estado_filtro and estado != estado_filtro:
            continue

        if saldo > 0:
            total_por_cobrar += saldo
        if estado == "vencida":
            cant_vencidas += 1
        if estado == "pendiente" and f.fecha_vencimiento:
            if prox_vencimiento is None or f.fecha_vencimiento < prox_vencimiento:
                prox_vencimiento = f.fecha_vencimiento

        comprobantes = [
            {
                "numero": ar.recibo_id,
                "fecha":  ar.recibo.fecha,
                "monto":  ar.monto_aplicado,
            }
            for ar in f.aplicaciones.all()
        ]

        filas.append({
            "obj":          f,
            "total":        total_fv,
            "cobrado":      f.cobrado,
            "saldo":        saldo,
            "estado":       estado,
            "comprobantes": comprobantes,
        })

    return render(request, "tem_administracion/cuenta_corriente_cliente.html", {
        "filas":             filas,
        "clientes":          clientes,
        "cliente_id":        cliente_id,
        "fecha_desde":       fecha_desde,
        "fecha_hasta":       fecha_hasta,
        "estado_filtro":     estado_filtro,
        "total_por_cobrar":  total_por_cobrar,
        "cant_vencidas":     cant_vencidas,
        "prox_vencimiento":  prox_vencimiento,
    })
