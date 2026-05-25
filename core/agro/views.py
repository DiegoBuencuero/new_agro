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
            return None
        raw  = r.text.replace('"volume":}', '"volume": null}')
        data = json.loads(raw)
        syms = data.get("symbols", [])
        if not syms:
            return None
        close = syms[0].get("close")
        return float(close) if close is not None else None
    except Exception:
        return None

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
            return None, None
        meta  = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        ts    = meta.get("regularMarketTime")  # unix timestamp
        fecha = None
        if ts:
            fecha = datetime.datetime.utcfromtimestamp(ts).strftime("%d/%m %H:%Mz")
        return (round(float(price), 4) if price is not None else None), fecha
    except Exception:
        return None, None

def _cents_to_usd_ton(cents):
    if cents is None:
        return None
    return round(cents / 100 * 36.744, 2)  # 1 bushel soja ≈ 27.2155 kg → 1000/27.2155 ≈ 36.74

def ajax_cotizaciones(request):
    soja_c  = _stooq_price(_STOOQ["soja"])
    maiz_c  = _stooq_price(_STOOQ["maiz"])
    trigo_c = _stooq_price(_STOOQ["trigo"])
    usd, usd_fecha = _usd_brl()

    def fmt(cents, kg_bushel):
        if cents is None:
            return None
        usd_bushel = cents / 100
        usd_ton    = round(usd_bushel / kg_bushel * 1000, 2)
        brl_saca   = round(usd_bushel * (60 / kg_bushel) * usd, 2) if usd else None
        return {"usd_ton": usd_ton, "brl_saca": brl_saca}

    return JsonResponse({
        "soja":      fmt(soja_c,  27.2155),
        "maiz":      fmt(maiz_c,  25.4012),
        "trigo":     fmt(trigo_c, 27.2155),
        "usd_brl":   usd,
        "usd_fecha": usd_fecha,
    })


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
        costo_act = ActividadProductiva.objects.filter(
            fase__ciclo=ciclo
        ).aggregate(t=Coalesce(Sum("total"), Decimal("0")))["t"]

        costo_ins = ActividadInsumo.objects.filter(
            actividad__fase__ciclo=ciclo
        ).aggregate(t=Coalesce(Sum("costo_total"), Decimal("0")))["t"]

        ha = ciclo.superficie_ha or Decimal("1")
        costo_ha = round(float((costo_act + costo_ins) / ha), 2)

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