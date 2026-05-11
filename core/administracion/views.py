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

from gestion_agro.models import FacturaCompra, Proveedor
from .models import Pago, AplicacionPago
from .forms import FiltroFacturasForm, AplicacionPagoForm


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
