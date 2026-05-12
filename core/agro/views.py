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
    from decimal import Decimal
    from django.db.models import Sum, Count
    from django.db.models.functions import Coalesce
    from gestion_agro.models import (
        CicloAgricola, FaseAgricola, ActividadProductiva,
        MovimientoStock, Producto,
    )
    from administracion.models import FacturaVenta, AplicacionRecibo

    empresa = getattr(request.user.profile, "empresa", None)
    if not empresa:
        return render(request, "index.html", {})

    # ── Ciclos ──────────────────────────────────────────────────────
    ciclos_activos = CicloAgricola.objects.filter(
        campo__empresa=empresa,
        fases__estado="abierto",
    ).distinct().count()

    ciclos_totales = CicloAgricola.objects.filter(campo__empresa=empresa).count()

    # ── Stock ───────────────────────────────────────────────────────
    productos_finales = Producto.objects.filter(empresa=empresa, producto_final=True)

    kg_cosechado = MovimientoStock.objects.filter(
        producto__in=productos_finales,
        tipo="ENTRADA",
        cosecha__isnull=False,
    ).aggregate(t=Coalesce(Sum("cantidad"), Decimal("0")))["t"]

    kg_en_stock = kg_cosechado - MovimientoStock.objects.filter(
        producto__in=productos_finales,
        tipo="VENTA",
    ).aggregate(t=Coalesce(Sum("cantidad"), Decimal("0")))["t"]

    # ── Ventas / Cobros ─────────────────────────────────────────────
    facturas = FacturaVenta.objects.filter(empresa=empresa).prefetch_related("items", "aplicaciones")
    total_ventas   = Decimal("0")
    total_cobrado  = Decimal("0")
    for f in facturas:
        tv = sum(i.cantidad * i.precio_unitario for i in f.items.all())
        tc = f.aplicaciones.aggregate(t=Coalesce(Sum("monto_aplicado"), Decimal("0")))["t"]
        total_ventas  += tv
        total_cobrado += tc
    por_cobrar = total_ventas - total_cobrado

    # ── Últimas actividades ─────────────────────────────────────────
    ultimas_actividades = (
        ActividadProductiva.objects
        .filter(fase__ciclo__campo__empresa=empresa)
        .select_related("tipo", "fase__ciclo__campo", "fase__ciclo__cultivo")
        .order_by("-fecha")[:8]
    )

    return render(request, "index.html", {
        "ciclos_activos":      ciclos_activos,
        "ciclos_totales":      ciclos_totales,
        "kg_cosechado":        kg_cosechado,
        "kg_en_stock":         kg_en_stock,
        "total_ventas":        total_ventas,
        "total_cobrado":       total_cobrado,
        "por_cobrar":          por_cobrar,
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