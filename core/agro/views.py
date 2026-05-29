from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from .forms import LoginForm, ConfiguracionEmpresaForm, RegistroForm

# ── Cotizaciones CBOT / USD ──────────────────────────────────────────────────

_STOOQ = {
    "soja":  "https://stooq.com/q/l/?s=zs.f&f=sd2t2ohlcv&h&e=json",
    "maiz":  "https://stooq.com/q/l/?s=zc.f&f=sd2t2ohlcv&h&e=json",
    "trigo": "https://stooq.com/q/l/?s=zw.f&f=sd2t2ohlcv&h&e=json",
}

def _stooq_price(url):
    try:
        import requests, json
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None, None
        raw  = r.text.replace('"volume":}', '"volume": null}')
        data = json.loads(raw)
        syms = data.get("symbols", [])
        if not syms:
            return None, None
        sym   = syms[0]
        close = sym.get("close")
        open_ = sym.get("open")
        return (float(close) if close is not None else None,
                float(open_) if open_ is not None else None)
    except Exception:
        return None, None

def _usd_brl():
    try:
        import requests, datetime
        session = requests.Session()
        session.get("https://finance.yahoo.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        r = session.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/USDBRL=X",
            params={"range": "7d", "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                     "Referer": "https://finance.yahoo.com/"},
            timeout=5,
        )
        if r.status_code != 200:
            return None, None, None
        meta  = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev  = meta.get("chartPreviousClose")
        ts    = meta.get("regularMarketTime")
        fecha = None
        if ts:
            fecha = datetime.datetime.utcfromtimestamp(ts).strftime("%d/%m %H:%Mz")
        return (round(float(price), 4) if price is not None else None), prev, fecha
    except Exception:
        return None, None, None

def _trend(close, ref):
    if close is None or ref is None or ref == 0:
        return None, None
    pct = (close - ref) / ref * 100
    direction = "up" if pct > 0.01 else ("down" if pct < -0.01 else "flat")
    return direction, round(abs(pct), 2)

def ajax_cotizaciones(request):
    soja_c,  soja_o  = _stooq_price(_STOOQ["soja"])
    maiz_c,  maiz_o  = _stooq_price(_STOOQ["maiz"])
    trigo_c, trigo_o = _stooq_price(_STOOQ["trigo"])
    usd, usd_prev, usd_fecha = _usd_brl()

    def fmt(cents, ref_cents, kg_bushel):
        if cents is None:
            return None
        usd_bushel = cents / 100
        usd_ton    = round(usd_bushel / kg_bushel * 1000, 2)
        brl_saca   = round(usd_bushel * (60 / kg_bushel) * usd, 2) if usd else None
        direction, pct = _trend(cents, ref_cents)
        return {"usd_ton": usd_ton, "brl_saca": brl_saca, "trend": direction, "pct": pct}

    usd_direction, usd_pct = _trend(usd, usd_prev)
    return JsonResponse({
        "soja":      fmt(soja_c,  soja_o,  27.2155),
        "maiz":      fmt(maiz_c,  maiz_o,  25.4012),
        "trigo":     fmt(trigo_c, trigo_o, 27.2155),
        "usd_brl":   usd,
        "usd_trend": usd_direction,
        "usd_pct":   usd_pct,
        "usd_fecha": usd_fecha,
    })


@login_required
def ajax_dashboard_resumen(request):
    import datetime
    from decimal import Decimal
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField
    from django.db.models.functions import Coalesce
    from gestion_agro.models import FacturaCompra
    from administracion.models import FacturaVenta, AplicacionRecibo

    empresa = getattr(request.user.profile, "empresa", None)
    if not empresa:
        return JsonResponse({"ok": False})

    hoy  = datetime.date.today()
    en30 = hoy + datetime.timedelta(days=30)

    a_pagar     = Decimal("0")
    pagar_30d   = Decimal("0")
    for f in FacturaCompra.objects.filter(empresa=empresa).prefetch_related("aplicaciones"):
        pagado = f.aplicaciones.aggregate(t=Coalesce(Sum("monto_aplicado"), Decimal("0")))["t"]
        saldo  = f.total - pagado
        if saldo <= 0:
            continue
        a_pagar += saldo
        if f.fecha_vencimiento and hoy <= f.fecha_vencimiento <= en30:
            pagar_30d += saldo

    a_cobrar    = Decimal("0")
    cobrar_30d  = Decimal("0")
    expr = ExpressionWrapper(F("cantidad") * F("precio_unitario"), output_field=DecimalField())
    for fv in FacturaVenta.objects.filter(empresa=empresa).prefetch_related("items", "aplicaciones"):
        total_fv = fv.items.aggregate(t=Coalesce(Sum(expr), Decimal("0")))["t"]
        cobrado  = fv.aplicaciones.aggregate(t=Coalesce(Sum("monto_aplicado"), Decimal("0")))["t"]
        saldo    = total_fv - cobrado
        if saldo <= 0:
            continue
        a_cobrar += saldo
        if fv.fecha_vencimiento and hoy <= fv.fecha_vencimiento <= en30:
            cobrar_30d += saldo

    return JsonResponse({
        "ok":         True,
        "a_cobrar":   float(a_cobrar),
        "a_pagar":    float(a_pagar),
        "saldo_neto": float(a_cobrar - a_pagar),
        "proyeccion": float(cobrar_30d - pagar_30d),
    })


@login_required
def ajax_dashboard_calendario(request):
    import datetime
    from decimal import Decimal
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField
    from django.db.models.functions import Coalesce, TruncMonth, TruncWeek
    from gestion_agro.models import FacturaCompra
    from administracion.models import FacturaVentaItem

    empresa = getattr(request.user.profile, "empresa", None)
    if not empresa:
        return JsonResponse({"ok": False})

    hoy  = datetime.date.today()
    modo = request.GET.get("modo", "mensual")
    expr = ExpressionWrapper(F("cantidad") * F("precio_unitario"), output_field=DecimalField())

    if modo == "semanal":
        year  = int(request.GET.get("year",  hoy.year))
        month = int(request.GET.get("month", hoy.month))
        inicio = datetime.date(year, month, 1)
        if month == 12:
            fim = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            fim = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

        pagos_qs = (
            FacturaCompra.objects
            .filter(empresa=empresa, fecha_vencimiento__gte=inicio, fecha_vencimiento__lte=fim)
            .annotate(semana=TruncWeek("fecha_vencimiento"))
            .values("semana")
            .annotate(total=Coalesce(Sum("total"), Decimal("0")))
            .order_by("semana")
        )
        from django.db.models import DateField
        cobros_qs = (
            FacturaVentaItem.objects
            .filter(factura__empresa=empresa)
            .annotate(fecha_ef=Coalesce("factura__fecha_vencimiento", "factura__fecha", output_field=DateField()))
            .filter(fecha_ef__gte=inicio, fecha_ef__lte=fim)
            .annotate(semana=TruncWeek("fecha_ef"))
            .values("semana")
            .annotate(total=Coalesce(Sum(expr), Decimal("0")))
            .order_by("semana")
        )
        pagos_dict  = {r["semana"].strftime("%d/%m"): float(r["total"]) for r in pagos_qs  if r["semana"]}
        cobros_dict = {r["semana"].strftime("%d/%m"): float(r["total"]) for r in cobros_qs if r["semana"]}
        labels = sorted(set(list(pagos_dict) + list(cobros_dict)))
        return JsonResponse({
            "ok": True, "modo": "semanal", "labels": labels,
            "pagos":  [pagos_dict.get(l, 0)  for l in labels],
            "cobros": [cobros_dict.get(l, 0) for l in labels],
        })

    # ── mensual: últimos 12 meses ─────────────────────────────
    inicio = (hoy - datetime.timedelta(days=365)).replace(day=1)
    pagos_qs = (
        FacturaCompra.objects
        .filter(empresa=empresa, fecha_vencimiento__gte=inicio)
        .annotate(mes=TruncMonth("fecha_vencimiento"))
        .values("mes")
        .annotate(total=Coalesce(Sum("total"), Decimal("0")))
        .order_by("mes")
    )
    from django.db.models import DateField
    cobros_qs = (
        FacturaVentaItem.objects
        .filter(factura__empresa=empresa)
        .annotate(fecha_ef=Coalesce("factura__fecha_vencimiento", "factura__fecha", output_field=DateField()))
        .filter(fecha_ef__gte=inicio)
        .annotate(mes=TruncMonth("fecha_ef"))
        .values("mes")
        .annotate(total=Coalesce(Sum(expr), Decimal("0")))
        .order_by("mes")
    )
    pagos_dict  = {r["mes"].strftime("%m/%Y"): float(r["total"]) for r in pagos_qs  if r["mes"]}
    cobros_dict = {r["mes"].strftime("%m/%Y"): float(r["total"]) for r in cobros_qs if r["mes"]}

    labels_set = set()
    cur = inicio
    while cur <= hoy:
        labels_set.add(cur.strftime("%m/%Y"))
        cur = cur.replace(month=cur.month % 12 + 1, year=cur.year + (1 if cur.month == 12 else 0))
    labels_set |= set(cobros_dict.keys()) | set(pagos_dict.keys())
    labels = sorted(labels_set, key=lambda s: (int(s.split('/')[1]), int(s.split('/')[0])))

    return JsonResponse({
        "ok": True, "modo": "mensual", "labels": labels,
        "pagos":  [pagos_dict.get(l, 0)  for l in labels],
        "cobros": [cobros_dict.get(l, 0) for l in labels],
    })


@login_required
def ajax_dashboard_vencimientos(request):
    import datetime
    from decimal import Decimal
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField
    from django.db.models.functions import Coalesce
    from gestion_agro.models import FacturaCompra
    from administracion.models import FacturaVenta

    empresa = getattr(request.user.profile, "empresa", None)
    if not empresa:
        return JsonResponse({"ok": False})

    hoy  = datetime.date.today()
    dias = int(request.GET.get("dias", 30))
    fin  = hoy + datetime.timedelta(days=dias)
    expr = ExpressionWrapper(F("cantidad") * F("precio_unitario"), output_field=DecimalField())

    items = []
    for f in (FacturaCompra.objects
              .filter(empresa=empresa, fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=fin)
              .prefetch_related("aplicaciones")
              .select_related("proveedor")):
        pagado = f.aplicaciones.aggregate(t=Coalesce(Sum("monto_aplicado"), Decimal("0")))["t"]
        saldo  = f.total - pagado
        if saldo <= 0:
            continue
        items.append({
            "tipo":    "pagar",
            "entidad": str(f.proveedor),
            "numero":  f.numero,
            "fecha":   f.fecha_vencimiento.strftime("%d/%m/%Y"),
            "dias":    (f.fecha_vencimiento - hoy).days,
            "monto":   float(saldo),
        })

    for fv in (FacturaVenta.objects
               .filter(empresa=empresa, fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=fin)
               .prefetch_related("items", "aplicaciones")
               .select_related("cliente")):
        total_fv = fv.items.aggregate(t=Coalesce(Sum(expr), Decimal("0")))["t"]
        cobrado  = fv.aplicaciones.aggregate(t=Coalesce(Sum("monto_aplicado"), Decimal("0")))["t"]
        saldo    = total_fv - cobrado
        if saldo <= 0:
            continue
        items.append({
            "tipo":    "cobrar",
            "entidad": str(fv.cliente),
            "numero":  fv.numero,
            "fecha":   fv.fecha_vencimiento.strftime("%d/%m/%Y"),
            "dias":    (fv.fecha_vencimiento - hoy).days,
            "monto":   float(saldo),
        })

    items.sort(key=lambda x: x["dias"])
    return JsonResponse({"ok": True, "items": items})


def login_page(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'GET':
        form = LoginForm()
        return render(request, 'login.html', {'form': form})

    form = LoginForm(request.POST)
    if form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect('/')

    messages.error(request, _('Usuario o contraseña incorrectos'))
    return render(request, 'login.html', {'form': form})



@login_required
def index(request):
    import json
    import datetime
    from decimal import Decimal
    from django.db.models import Sum
    from django.db.models.functions import Coalesce
    from django.utils import timezone
    from gestion_agro.models import (
        CicloAgricola, ActividadProductiva, ActividadInsumo,
        MovimientoStock, Producto, FacturaCompra, Campo,
    )
    from administracion.models import AplicacionPago
    from mapas.models import IndiceVegetacion

    empresa = getattr(request.user.profile, "empresa", None)
    if not empresa:
        return render(request, "index.html", {})

    hoy    = timezone.now().date()
    hace20 = hoy - datetime.timedelta(days=20)
    en30   = hoy + datetime.timedelta(days=30)

    # ── Ciclos ────────────────────────────────────────────────────────
    ciclos_abiertos = list(
        CicloAgricola.objects
        .filter(campo__empresa=empresa, fecha_fin__isnull=True)
        .distinct()
        .select_related("campo", "cultivo")
        .order_by("campo__nombre")
    )
    ciclos_cerrados = list(
        CicloAgricola.objects
        .filter(campo__empresa=empresa, fecha_fin__isnull=False)
        .distinct()
        .select_related("campo", "cultivo")
        .order_by("-fecha_fin")[:5]
    )

    # ── Costo por ciclo abierto ───────────────────────────────────────
    ciclos_data = []
    for ciclo in ciclos_abiertos:
        agg = ActividadProductiva.objects.filter(
            fase__ciclo=ciclo
        ).aggregate(
            mo=Coalesce(Sum("total_mo"),  Decimal("0")),
            maq=Coalesce(Sum("total_maq"), Decimal("0")),
        )
        costo_mo  = agg["mo"]
        costo_maq = agg["maq"]
        costo_ins = ActividadInsumo.objects.filter(
            actividad__fase__ciclo=ciclo
        ).aggregate(t=Coalesce(Sum("costo_total"), Decimal("0")))["t"]

        ha = ciclo.superficie_ha or Decimal("1")
        costo_total = costo_mo + costo_maq + costo_ins
        costo_ha = round(float(costo_total / ha), 2)

        nom = (ciclo.cultivo.nombre or "").lower()
        if "soja" in nom:
            commodity = "soja"
        elif "maíz" in nom or "maiz" in nom:
            commodity = "maiz"
        elif "trigo" in nom:
            commodity = "trigo"
        else:
            commodity = None

        ciclos_data.append({
            "id":        ciclo.id,
            "campo":     ciclo.campo.nombre,
            "cultivo":   ciclo.cultivo.nombre if ciclo.cultivo else "—",
            "ha":        float(ha),
            "costo_ha":  costo_ha,
            "mo_ha":     round(float(costo_mo  / ha), 2),
            "maq_ha":    round(float(costo_maq / ha), 2),
            "ins_ha":    round(float(costo_ins / ha), 2),
            "commodity": commodity,
        })

    # ── Stock de granos por producto ──────────────────────────────────
    granos_stock = []
    for prod in Producto.objects.filter(empresa=empresa, producto_final=True):
        entrada = MovimientoStock.objects.filter(
            producto=prod, tipo="ENTRADA", cosecha__isnull=False
        ).aggregate(t=Coalesce(Sum("cantidad"), Decimal("0")))["t"]
        salida = MovimientoStock.objects.filter(
            producto=prod, tipo="VENTA"
        ).aggregate(t=Coalesce(Sum("cantidad"), Decimal("0")))["t"]
        kg = float(entrada - salida)
        if kg > 0:
            granos_stock.append({
                "nombre": prod.nombre,
                "sc":     round(kg / 60, 1),
                "kg":     round(kg, 0),
            })

    # ── Deuda proveedores ─────────────────────────────────────────────
    deuda_total   = Decimal("0")
    deuda_vencida = Decimal("0")
    deuda_proxima = Decimal("0")
    alertas_facturas = []

    for f in FacturaCompra.objects.filter(empresa=empresa).prefetch_related("aplicaciones"):
        pagado = f.aplicaciones.aggregate(t=Coalesce(Sum("monto_aplicado"), Decimal("0")))["t"]
        saldo  = f.total - pagado
        if saldo <= 0:
            continue
        deuda_total += saldo
        if f.fecha_vencimiento:
            if f.fecha_vencimiento < hoy:
                deuda_vencida += saldo
                alertas_facturas.append({
                    "proveedor":   str(f.proveedor),
                    "numero":      f.numero,
                    "saldo":       float(saldo),
                    "vencimiento": f.fecha_vencimiento.strftime("%d/%m/%Y"),
                    "dias":        (hoy - f.fecha_vencimiento).days,
                })
            elif f.fecha_vencimiento <= en30:
                deuda_proxima += saldo

    # ── Alerta: ciclos sin actividad ──────────────────────────────────
    alertas_inactivos = []
    for ciclo in ciclos_abiertos:
        ultima = (
            ActividadProductiva.objects
            .filter(fase__ciclo=ciclo)
            .order_by("-fecha")
            .values_list("fecha", flat=True)
            .first()
        )
        if ultima is None or ultima < hace20:
            alertas_inactivos.append({
                "campo":   ciclo.campo.nombre,
                "cultivo": ciclo.cultivo.nombre if ciclo.cultivo else "—",
                "dias":    (hoy - ultima).days if ultima else None,
                "id":      ciclo.id,
            })

    # ── Alerta: NDVI en caída ─────────────────────────────────────────
    alertas_ndvi = []
    for campo in Campo.objects.filter(empresa=empresa):
        indices = list(
            IndiceVegetacion.objects
            .filter(captura__campo=campo, tipo="ndvi")
            .order_by("-captura__fecha")
            .values_list("promedio", flat=True)[:2]
        )
        if len(indices) == 2:
            actual, anterior = indices[0], indices[1]
            if anterior > 0 and (anterior - actual) / anterior > 0.15:
                alertas_ndvi.append({
                    "campo":    campo.nombre,
                    "actual":   round(actual, 3),
                    "anterior": round(anterior, 3),
                    "caida":    round((anterior - actual) / anterior * 100, 1),
                })

    # ── Últimas actividades ───────────────────────────────────────────
    ultimas_actividades = (
        ActividadProductiva.objects
        .filter(fase__ciclo__campo__empresa=empresa)
        .select_related("tipo", "fase__ciclo__campo", "fase__ciclo__cultivo")
        .order_by("-fecha")[:8]
    )

    total_alertas = len(alertas_facturas) + len(alertas_inactivos) + len(alertas_ndvi)

    # Ciclos cerrados para el panel lateral
    ciclos_cerrados_data = [
        {
            "campo":    c.campo.nombre,
            "cultivo":  c.cultivo.nombre if c.cultivo else "—",
            "fecha_fin": c.fecha_fin.strftime("%d/%m/%Y") if c.fecha_fin else "",
        }
        for c in ciclos_cerrados
    ]

    return render(request, "index.html", {
        "ciclos_count":        len(ciclos_abiertos),
        "ciclos_totales":      len(ciclos_abiertos) + len(ciclos_cerrados),
        "ciclos_data_json":    json.dumps(ciclos_data),
        "ciclos_cerrados_json": json.dumps(ciclos_cerrados_data),
        "granos_stock":        granos_stock,
        "deuda_total":         deuda_total,
        "deuda_vencida":       deuda_vencida,
        "deuda_proxima":       deuda_proxima,
        "alertas_facturas":    alertas_facturas,
        "alertas_inactivos":   alertas_inactivos,
        "alertas_ndvi":        alertas_ndvi,
        "total_alertas":       total_alertas,
        "ultimas_actividades": ultimas_actividades,
    })


def vista_registro(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                from agro.models import Moneda
                moneda = Moneda.objects.first()
                if not moneda:
                    messages.error(request, _("El sistema no tiene monedas configuradas. Contacte al administrador."))
                    return render(request, "registro.html", {"form": form})

                with transaction.atomic():
                    from agro.models import Empresa
                    empresa = Empresa.objects.create(
                        nombre=cd["empresa_nombre"],
                        razon_social=cd["empresa_razon_social"],
                        cuit=cd["empresa_cuit"],
                        moneda=moneda,
                        status="O",
                    )
                    from django.contrib.auth.models import User
                    user = User.objects.create_user(
                        username=cd["username"],
                        email=cd["email"],
                        password=cd["password1"],
                    )
                    user.profile.empresa = empresa
                    user.profile.tipo = "A"
                    user.profile.status = "A"
                    user.profile.save()

                messages.success(request, _("Cuenta creada correctamente. Podés ingresar ahora."))
                return redirect("login")
            except Exception:
                messages.error(request, _("Error al crear la cuenta. Intentá nuevamente."))
    else:
        form = RegistroForm()

    return render(request, "registro.html", {"form": form})


def vista_cuenta_suspendida(request):
    return render(request, "cuenta_suspendida.html")


@login_required
def vista_configuracion(request):
    empresa = request.user.profile.empresa

    if request.method == "POST":
        form = ConfiguracionEmpresaForm(empresa, request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, _("Configuración guardada correctamente"))
            return redirect("vista_configuracion")
        else:
            messages.error(request, _("Corrija los errores del formulario"))
    else:
        form = ConfiguracionEmpresaForm(empresa, instance=empresa)

    return render(request, "configuracion.html", {"form": form, "empresa": empresa})