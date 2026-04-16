from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import pdfplumber
from typing import Any, Dict, List, Optional, Tuple
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from gestion_agro.models import ( MovimientoStock, FaseAgricola, ActividadProductiva,
                                 
)

def obtener_valores_costos(tipo, subtipo, empresa):
    v_mo = None
    v_mq = None
    c_mo = None
    c_mq = None

    # primero subtipo
    if subtipo:
        if subtipo.valor_x_ha_mo is not None:
            v_mo = subtipo.valor_x_ha_mo
        if subtipo.valor_x_ha_mq is not None:
            v_mq = subtipo.valor_x_ha_mq

        if subtipo.valor_mo not in (None, 0):
            c_mo = subtipo.valor_mo
        if subtipo.valor_maquina not in (None, 0):
            c_mq = subtipo.valor_maquina

    # despues tipo
    if v_mq is None:
        v_mq = tipo.valor_x_ha_mq

    if c_mq in (None, 0):
        c_mq = tipo.valor_maquina

    # por ultimo empresa
    if empresa:
        if c_mo in (None, 0):
            c_mo = empresa.valor_mobra
        if c_mq in (None, 0):
            c_mq = empresa.valor_maquina

    return v_mo, v_mq, c_mo, c_mq

def calcular_costos_actividad(
    tipo,
    subtipo,
    empresa,
    actividad,
    insumos,
    v_mo_input=None,
    v_mq_input=None,
    c_mo_input=None,
    c_mq_input=None,
):
    costo_insumos = 0
    horas_hombre = 0
    costo_mo = 0
    horas_maquina = 0
    costo_mq = 0

    # superficie desde la relación
    superficie = actividad.fase.ciclo. superficie_ha

    # valores base
    v_mo, v_mq, c_mo_unit, c_mq_unit = obtener_valores_costos(tipo, subtipo, empresa)

    # prioridad a valores ingresados
    if v_mo_input is not None:
        v_mo = v_mo_input

    if v_mq_input is not None:
        v_mq = v_mq_input

    if c_mo_input not in (None, 0):
        c_mo_unit = c_mo_input

    if c_mq_input not in (None, 0):
        c_mq_unit = c_mq_input

    # insumos
    for insumo in insumos or []:
        if insumo.producto:
            cantidad = insumo.dosis * actividad.fase.ciclo.superficie_ha
            costo_insumos += cantidad * insumo.producto.precio

    # mano de obra
    if v_mo is not None and c_mo_unit is not None:
        horas_hombre = v_mo * superficie
        costo_mo = horas_hombre * c_mo_unit

    # máquina
    if v_mq is not None and c_mq_unit is not None:
        horas_maquina = v_mq * superficie
        costo_mq = horas_maquina * c_mq_unit

    total = costo_insumos + costo_mo + costo_mq

    return costo_insumos, horas_hombre, costo_mo, horas_maquina, costo_mq, total

def obtener_reglas_de_fase(tipo, subtipo):
    # de donde saco si abre o cierra fase
    af = None
    cf = None

    if subtipo:
        if subtipo.abre_fase is not None:
            af = subtipo.abre_fase
        if subtipo.cierra_fase is not None:
            cf = subtipo.cierra_fase
     
    if not af:
        af = tipo.abre_fase
    if not cf:
        cf = tipo.cierra_fase

    return af, cf

def validar_reglas_generales(ciclo, fase, tipo, subtipo, fecha,  abre_fase):
    # validaciones base del flujo
    if fecha < ciclo.fecha_inicio:
        return False, _("La fecha es anterior al inicio del ciclo.")

    if tipo.requiere_subtipo and not subtipo:
        return False, _("Debe seleccionar un subtipo.")

    if not fase and not  abre_fase:
        return False, _("No hay fase abierta y esta actividad no puede abrir una.")

    if fase and fase.estado == "abierto" and fecha < fase.fecha_inicio:
        return False, _("La fecha es menor al inicio de la fase.")

    if fase and fase.estado == "cerrado" and not  abre_fase:
        return False, _("La fase está cerrada y esta actividad no puede abrir una nueva.")

    return True, None

def validar_insumos(tipo, insumo_formset):
    # chequeo que tenga insumos si corresponde
    if not tipo.requiere_insumo:
        return True, None

    if not insumo_formset.is_valid():
        return False, _("Hay errores en los insumos.")

    hay_insumos = False

    for formulario in insumo_formset:
        if hasattr(formulario, "cleaned_data"):
            if formulario.cleaned_data and not formulario.cleaned_data.get("DELETE", False):
                hay_insumos = True
                break

    if not hay_insumos:
        return False, _("Debe cargar al menos un insumo.")

    return True, None

def validar_monitoreo(tipo, vistoria_form):
    # valida vistoria si aplica
    if not tipo.requiere_vist:
        return True, None

    if not vistoria_form or not vistoria_form.is_valid():
        return False, _("Hay errores en los datos de monitoreo.")

    return True, None

def validar_cosecha(ciclo, tipo, fecha, cosecha_form):
    # valida cosecha y que exista siembra previa
    if not tipo.requiere_cosecha:
        return True, None

    if not cosecha_form or not cosecha_form.is_valid():
        return False, _("Hay errores en los datos de cosecha.")

    existe_siembra = ActividadProductiva.objects.filter(
        fase__ciclo=ciclo,
        tipo__nombre__iexact="Siembra",
        fecha__lte=fecha,
    ).exists()

    if not existe_siembra:
        return False, _("No se puede registrar cosecha sin una siembra previa.")

    return True, None

def validar_reglas_siembra(fase, tipo, subtipo):
    # reglas propias de siembra
    if tipo.nombre.lower() != "siembra":
        return True, None

    nombre_subtipo = subtipo.nombre.lower() if subtipo else ""

    existe_principal = ActividadProductiva.objects.filter(
        fase=fase,
        tipo=tipo,
        subtipo__nombre__iexact="Cultivo principal",
    ).exists()

    existe_cobertura = ActividadProductiva.objects.filter(
        fase=fase,
        tipo=tipo,
        subtipo__nombre__iexact="Cobertura",
    ).exists()

    existe_misma_siembra = ActividadProductiva.objects.filter(
        fase=fase,
        tipo=tipo,
        subtipo=subtipo,
    ).exists()

    if existe_misma_siembra:
        return False, _("Ya existe una siembra de este subtipo en la fase actual.")

    if nombre_subtipo == "cultivo principal" and existe_cobertura:
        return False, _("No se permite cultivo principal y cobertura en la misma fase.")

    if nombre_subtipo == "cobertura" and existe_principal:
        return False, _("No se permite cobertura y cultivo principal en la misma fase.")

    if nombre_subtipo == "resiembra" and not existe_principal:
        return False, _("La resiembra solo se permite si ya existe cultivo principal en la fase.")

    return True, None

def validar_reglas_aplicacion(fase, tipo, subtipo, fecha):
    # evita duplicados exactos en aplicaciones
    if tipo.nombre.lower() != "aplicación" or not fase:
        return True, None

    existe_misma_aplicacion = ActividadProductiva.objects.filter(
        fase=fase,
        tipo=tipo,
        subtipo=subtipo,
        fecha=fecha,
    ).exists()

    if existe_misma_aplicacion:
        return False, _("Ya existe una aplicación de este tipo en la misma fecha y fase.")

    return True, None

def crear_fase_si_corresponde(ciclo, fase, fecha,  abre_fase):
    # si la actividad abre fase y hace falta, la creo
    inicio_fase = False

    if  abre_fase and (not fase or fase.estado == "cerrado"):
        fase = FaseAgricola.objects.create(
            ciclo=ciclo,
            tipo="PRI",
            fecha_inicio=fecha,
            estado="abierto",
        )
        inicio_fase = True

    return fase, inicio_fase

def cerrar_fase_si_corresponde(fase, fecha,  cierra_fase):
    # si corresponde, cierro la fase
    if  cierra_fase and fase and fase.estado == "abierto":
        fase.fecha_fin = fecha
        fase.estado = "cerrado"
        fase.save()

def obtener_capas_stock(producto, metodo="FIFO"):
    entradas = list(
        MovimientoStock.objects
        .filter(
            producto=producto,
            tipo=MovimientoStock.Tipo.ENTRADA,
        )
        .order_by("fecha", "id")
        .values("id", "fecha", "cantidad", "precio_unitario")
    )

    salidas = list(
        MovimientoStock.objects
        .filter(
            producto=producto,
            tipo=MovimientoStock.Tipo.SALIDA,
        )
        .order_by("fecha", "id")
        .values("id", "fecha", "cantidad")
    )

    capas = []
    for e in entradas:
        capas.append({
            "movimiento_id": e["id"],
            "fecha": e["fecha"],
            "precio_unitario": e["precio_unitario"],
            "cantidad_original": e["cantidad"],
            "cantidad_disponible": e["cantidad"],
        })

    for s in salidas:
        pendiente = s["cantidad"]

        if metodo == "FIFO":
            recorrido = capas
        elif metodo == "LIFO":
            recorrido = list(reversed(capas))
        else:
            raise ValueError("Método inválido. Debe ser 'FIFO' o 'LIFO'.")

        for capa in recorrido:
            if pendiente <= 0:
                break

            disponible = capa["cantidad_disponible"]
            if disponible <= 0:
                continue

            consumir = min(disponible, pendiente)
            capa["cantidad_disponible"] -= consumir
            pendiente -= consumir

        if pendiente > 0:
            raise ValueError(
                f"Las salidas históricas del producto {producto.id} superan las entradas disponibles."
            )

    return capas

def calcular_costo_salida(producto, cantidad_salida, metodo="FIFO"):
    cantidad_salida = Decimal(cantidad_salida)
    capas = obtener_capas_stock(producto, metodo=metodo)

    pendiente = cantidad_salida
    costo_total = Decimal("0")
    detalle = []

    if metodo == "FIFO":
        recorrido = capas
    elif metodo == "LIFO":
        recorrido = list(reversed(capas))
    else:
        raise ValueError("Método inválido. Debe ser 'FIFO' o 'LIFO'.")

    for capa in recorrido:
        if pendiente <= 0:
            break

        disponible = capa["cantidad_disponible"]
        if disponible <= 0:
            continue

        consumir = min(disponible, pendiente)
        costo_parcial = consumir * capa["precio_unitario"]

        detalle.append({
            "movimiento_entrada_id": capa["movimiento_id"],
            "cantidad": consumir,
            "precio_unitario": capa["precio_unitario"],
            "costo_parcial": costo_parcial,
        })

        costo_total += costo_parcial
        pendiente -= consumir

    if pendiente > 0:
        raise ValueError("Stock insuficiente para realizar la salida.")

    precio_promedio = (
        costo_total / cantidad_salida if cantidad_salida > 0 else Decimal("0")
    )

    return {
        "costo_total": costo_total,
        "precio_promedio": precio_promedio,
        "detalle": detalle,
    }

def guardar_insumos_y_stock(actividad, tipo, insumo_formset, empresa):
    # si no requiere insumos, no hace nada
    if not tipo.requiere_insumo:
        return []

    insumo_formset.instance = actividad
    insumos = insumo_formset.save()

    # superficie desde relación
    superficie = actividad.fase.ciclo.superficie_ha 

    if empresa.calculo_costo == "F":
        metodo = "FIFO"
    elif empresa.calculo_costo == "L":
        metodo = "LIFO"
    else:
        metodo = "FIFO"  # default

    # registrar salida de stock
    for insumo in insumos:
        if insumo.producto:
            cantidad = insumo.dosis * superficie

            algo = calcular_costo_salida(insumo.producto, cantidad, metodo= metodo)  # valida que haya stock suficiente
            
            MovimientoStock.objects.create(
                producto=insumo.producto,
                tipo="SALIDA",
                cantidad=cantidad,
                um=insumo.um,
                fecha=timezone.now(),
                actividad=actividad,
                precio_unitario=algo["precio_promedio"],
            )
            insumo.cantidad_real = cantidad
            insumo.costo_total   = algo["costo_total"]
            insumo.costo_ha      = algo["costo_total"] / superficie if superficie else Decimal("0")
            insumo.save()

    return insumos

def guardar_monitoreo(actividad, tipo, vistoria_form):
    # guarda datos de monitoreo
    if not tipo.requiere_vist or not vistoria_form:
        return

    vistoria = vistoria_form.save(commit=False)
    vistoria.actividad = actividad
    vistoria.save()

def guardar_cosecha(actividad, tipo, cosecha_form):
    # guarda datos de cosecha
    if not tipo.requiere_cosecha or not cosecha_form:
        return

    cosecha = cosecha_form.save(commit=False)
    cosecha.actividad = actividad
    cosecha.save()
    
def registrar_actividad_aux(
    ciclo,
    fase,
    empresa,
    actividad_form,
    insumo_formset,
    vistoria_form=None,
    cosecha_form=None,
):
    tipo = actividad_form.cleaned_data["tipo"]
    subtipo = actividad_form.cleaned_data.get("subtipo")
    fecha = actividad_form.cleaned_data["fecha"]

    # 1. reglas de fase
    abre_fase, cierra_fase = obtener_reglas_de_fase(tipo, subtipo)

    # 2. validaciones generales
    ok, msg = validar_reglas_generales(ciclo, fase, tipo, subtipo, fecha, abre_fase)
    if not ok:
        return False, msg

    # 3. insumos
    ok, msg = validar_insumos(tipo, insumo_formset)
    if not ok:
        return False, msg

    # 4. monitoreo
    ok, msg = validar_monitoreo(tipo, vistoria_form)
    if not ok:
        return False, msg

    # 5. cosecha
    ok, msg = validar_cosecha(ciclo, tipo, fecha, cosecha_form)
    if not ok:
        return False, msg

    # 6. crear fase si corresponde
    fase, inicio_fase = crear_fase_si_corresponde(ciclo, fase, fecha, abre_fase)

    # 7. reglas de siembra
    ok, msg = validar_reglas_siembra(fase, tipo, subtipo)
    if not ok:
        return False, msg

    # 8. reglas de aplicación
    ok, msg = validar_reglas_aplicacion(fase, tipo, subtipo, fecha)
    if not ok:
        return False, msg

    # 9. guardar actividad
    actividad = actividad_form.save(commit=False)
    actividad.fase = fase
    actividad.save()

    # 10. guardar insumos y stock
    insumos = guardar_insumos_y_stock(actividad, tipo, insumo_formset, empresa)

    # 11. calcular costos
    costo_insumos, horas_hombre, costo_mo, horas_maquina, costo_mq, total = calcular_costos_actividad(
        tipo,
        subtipo,
        empresa,
        actividad,
        insumos,
    )

    # 12. guardar horas y valores en actividad
    v_mo, v_mq, c_mo_unit, c_mq_unit = obtener_valores_costos(tipo, subtipo, empresa)

    actividad.cantidad_hombre = horas_hombre
    actividad.valor_hombre = c_mo_unit or 0
    actividad.cantidad_h_maq = horas_maquina
    actividad.valor_h_maq = c_mq_unit or 0
    actividad.save()
    # agregue total de mo y maq para historicos
    actividad.total_mo  = horas_hombre  * (c_mo_unit  or Decimal("0"))
    actividad.total_maq = horas_maquina * (c_mq_unit  or Decimal("0"))
    actividad.total     = actividad.total_mo + actividad.total_maq
    actividad.save()

    # 13. guardar extras
    guardar_monitoreo(actividad, tipo, vistoria_form)
    guardar_cosecha(actividad, tipo, cosecha_form)

    # 14. cerrar fase
    cerrar_fase_si_corresponde(fase, fecha, cierra_fase)

    return True, {
        "actividad": actividad,
        "inicio_fase": inicio_fase,
    }


RE_DATE    = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RE_EMISSAO = re.compile(r"\bEMISS[ÃA]O\b\s*:?\s*(\d{2}/\d{2}/\d{4})", re.I)
RE_CODE    = re.compile(r"^\d{6,8}$")
RE_QTD_3DEC = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{3}$")
RE_MONEY   = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2,4}$")
RE_FOOTER  = re.compile(r"^\s*(INFORMAÇÕES COMPLEMENTARES|RESERVADO AO FISCO|CÁLCULO DO ISSQN)\b", re.I)

UNIT_SET = {"pc", "un", "kg", "lt", "l", "cx", "sc", "und", "pct", "bld", "gl"}


# ── PDF parser ───────────────────────────────────────────────────────────────

def group_words_by_line(words: List[Dict[str, Any]], y_tol: float = 3.0) -> List[Dict[str, Any]]:
    rows: Dict[float, List[Dict[str, Any]]] = {}
    for w in words:
        y = round(w["top"] / y_tol) * y_tol
        rows.setdefault(y, []).append(w)

    out = []
    for y in sorted(rows.keys()):
        row = sorted(rows[y], key=lambda a: a["x0"])
        text = " ".join(w["text"] for w in row)
        out.append({"y": y, "words": row, "text": text})
    return out

def find_table_range(rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    start = -1
    end = len(rows)

    for i, r in enumerate(rows):
        t = r["text"].upper()
        if "DADOS DO PRODUTO" in t:
            start = i + 1
            break

    if start == -1:
        start = 0

    for i in range(start, len(rows)):
        t = rows[i]["text"]
        if RE_FOOTER.match(t):
            end = i
            break

    return start, end

def extract_nfe_number_from_lines(lines: List[str]) -> Optional[str]:
    for i, ln in enumerate(lines):
        m = re.search(r"\bN[ºO]\b\s*(\d{4,10})\b", ln, re.I)
        if m:
            return m.group(1)

        up = ln.upper().strip()
        if up == "NF-E" or "NF-E" in up:
            for j in range(i, min(i + 6, len(lines))):
                m2 = re.search(r"\b(\d{4,10})\b", lines[j])
                if m2 and "/" not in lines[j] and "-" not in lines[j]:
                    window = " ".join(lines[i:j+1]).upper()
                    if "Nº" in window or "N°" in window or "N " in window:
                        return m2.group(1)

    for ln in lines:
        m = re.search(r"NUM\.\s*FAT\.\s*:\s*0*(\d{4,10})", ln, re.I)
        if m:
            return m.group(1)

    return None

def extract_provider_from_lines(lines: List[str]) -> Optional[str]:
    for i, ln in enumerate(lines):
        if ln.strip().upper() == "RECEBEMOS":
            for j in range(i + 1, min(i + 6, len(lines))):
                cand = lines[j].strip()
                if len(cand) >= 20 and any(ch.isalpha() for ch in cand):
                    if "PRODUTOS" in cand.upper() or "SERVIÇOS" in cand.upper():
                        continue
                    return cand

    for ln in lines:
        if "COOPERATIVA" in ln.upper() and len(ln.strip()) >= 20:
            return ln.strip()

    return None

def extract_emission_date(full_text: str) -> Optional[str]:
    m = RE_EMISSAO.search(full_text)
    return m.group(1) if m else None

def parse_item_row(tokens: List[str]) -> Optional[Dict[str, Any]]:
    if not tokens or not RE_CODE.match(tokens[0]):
        return None

    codigo = tokens[0]

    unit_idx = None
    for i in range(1, len(tokens) - 1):
        if tokens[i].lower() in UNIT_SET and RE_QTD_3DEC.match(tokens[i + 1]):
            unit_idx = i
            break

    if unit_idx is None:
        return None

    descricao = " ".join(tokens[1:unit_idx]).strip()
    unidade   = tokens[unit_idx]
    quantidade = tokens[unit_idx + 1]

    right  = tokens[unit_idx + 2:]
    monies = [t for t in right if RE_MONEY.match(t)]
    v_unit  = monies[0] if len(monies) >= 1 else None
    v_total = monies[1] if len(monies) >= 2 else None

    return {
        "codigo":    codigo,
        "descricao": descricao,
        "unidade":   unidade,
        "quantidade": quantidade,
        "v_unit":    v_unit,
        "v_total":   v_total,
    }

def parse_nfe_pdf(pdf_path: str) -> Dict[str, Any]:
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]

        full_text = page.extract_text() or ""
        lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]

        proveedor    = extract_provider_from_lines(lines)
        numero_nfe   = extract_nfe_number_from_lines(lines)
        fecha_emision = extract_emission_date(full_text)

        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
        rows  = group_words_by_line(words, y_tol=3.0)

        start, end   = find_table_range(rows)
        table_rows   = rows[start:end]

        items: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for r in table_rows:
            tokens = [w["text"] for w in r["words"]]
            text   = r["text"].strip()

            if RE_FOOTER.match(text):
                break

            parsed = parse_item_row(tokens)
            if parsed:
                if current:
                    items.append(current)
                current = parsed
                continue

            if current:
                up = text.upper()
                if "(" in text and "**" in text:
                    continue
                if " LOTE:" in up or " SAFRA:" in up or " RENASEM:" in up:
                    continue
                if "IBPT" in up or "VAL APROX" in up or "FONTE:" in up:
                    continue
                if RE_FOOTER.match(text):
                    break
                current["descricao"] = (current["descricao"] + " " + text).strip()

        if current:
            items.append(current)

        return {
            "proveedor":    proveedor,
            "numero_nfe":   numero_nfe,
            "fecha_emision": fecha_emision,
            "items":        items,
        }

# ── Helpers de matching ──────────────────────────────────────────────────────

def _score(descripcion: str, producto) -> int:
    desc = descripcion.lower().strip()
    prod = producto.nombre.lower().strip()
    if desc == prod:
        return 100
    if desc in prod or prod in desc:
        return 80
    palabras_desc = set(re.split(r"\W+", desc)) - {"", "de", "da", "do", "el", "la", "los", "e"}
    palabras_prod = set(re.split(r"\W+", prod)) - {"", "de", "da", "do", "el", "la", "los", "e"}
    if not palabras_desc:
        return 0
    comunes = palabras_desc & palabras_prod
    return int(len(comunes) / len(palabras_desc) * 70)

def _buscar_candidatos(descripcion: str, empresa, top_n: int = 4, umbral: int = 35):
    from gestion_agro.models import Producto
    if not descripcion:
        return []

    palabras = [p for p in descripcion.split() if len(p) >= 4]
    qs = Producto.objects.filter(empresa=empresa, activo=True)

    if palabras:
        from django.db.models import Q
        filtro = Q()
        for p in palabras[:4]:
            filtro |= Q(nombre__icontains=p)
        qs = qs.filter(filtro)

    candidatos = []
    for producto in qs.select_related("categoria")[:50]:
        s = _score(descripcion, producto)
        if s >= umbral:
            candidatos.append({"producto": producto, "score": s})

    candidatos.sort(key=lambda x: x["score"], reverse=True)
    return candidatos[:top_n]

def _detectar_contenido_unidad(descripcion: str, unidad_factura: str):
    """
    Retorna (contenido, unidad_base, nombre_presentacion)
    """
    desc = (descripcion or "").upper()
    unid = (unidad_factura or "").upper()

    mapa_unidad = {
        "BLD": ("bld", "L"),
        "GL":  ("gl",  "L"),
        "TON": ("ton", "TON"),
        "PC":  ("pc",  "KG"),
        "SC":  ("sc",  "KG"),
        "L":   ("l",   "L"),
        "KG":  ("kg",  "KG"),
        "UN":  ("un",  "UN"),
        "LT":  ("lt",  "L"),
        "GR":  ("gr",  "G"),
        "ML":  ("ml",  "ML"),
    }

    # Buscar número + unidad en la descripción
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(LITROS?|LITRO|KG|TON|GRAMAS?|GRAMA|ML)\b",
        desc,
        re.IGNORECASE,
    )

    if match:
        contenido = float(match.group(1).replace(",", "."))
        u = match.group(2).upper()
        unidad_base = {
            "LITROS": "L", "LITRO": "L",
            "GRAMAS": "G", "GRAMA": "G",
            "TON": "TON",
        }.get(u, u)
        pres_nome = unid.lower() if unid else unidad_base.lower()
        return contenido, unidad_base, pres_nome

    # Sin número en descripción — usar unidad de factura
    if unid in mapa_unidad:
        pres_nome, unidad_base = mapa_unidad[unid]

        # Semillas en PC: buscar "Unid Kg: 931"
        if unid == "PC":
            kg_match = re.search(r"UNID\s*KG[:\s]+(\d+(?:[.,]\d+)?)", desc)
            if kg_match:
                contenido = float(kg_match.group(1).replace(",", "."))
                return contenido, "KG", "pc"

        return 1.0, unidad_base, pres_nome

    # Fallback
    return 1.0, "UN", unid.lower() or "un"

# ── API AJAX ─────────────────────────────────────────────────────────────────

@login_required
def api_presentaciones(request):
    """
    GET /gestion/api/presentaciones/?producto_id=<id>
    Retorna las presentaciones de un producto en JSON.
    """
    from gestion_agro.models import PresentacionProducto

    producto_id = request.GET.get("producto_id")
    if not producto_id:
        return JsonResponse([], safe=False)

    empresa = request.user.profile.empresa

    presentaciones = (
        PresentacionProducto.objects
        .filter(producto_id=producto_id, producto__empresa=empresa)
        .order_by("nombre")
        .values("id", "nombre", "contenido", "unidad_factura")
    )

    data = [
        {
            "id":             p["id"],
            "nombre":         p["nombre"],
            "contenido":      str(p["contenido"]),
            "unidad_factura": p["unidad_factura"],
        }
        for p in presentaciones
    ]

    return JsonResponse(data, safe=False)

# ── Helper numérico ──────────────────────────────────────────────────────────

def br_to_float(valor):
    if not valor:
        return None
    try:
        return float(str(valor).replace(".", "").replace(",", "."))
    except ValueError:
        return None
