"""
Lectura de notas fiscales de compra.

- XML de NF-e: se lee directo (formato estándar, exacto, sin costo).
- PDF o imagen (DANFE, foto del celular, cualquier layout): se envía a Claude.

Devuelve siempre el mismo formato que usaba parse_nfe_pdf, para no tocar
la pantalla de revisión:

{
    "proveedor":       "RAZON SOCIAL",
    "proveedor_cnpj":  "83158824000111",
    "numero_nfe":      "898448",
    "serie":           "1",
    "chave_acesso":    "4225...",        # 44 dígitos o ""
    "fecha_emision":   "dd/mm/aaaa",
    "items": [
        {"codigo", "descricao", "unidade", "quantidade", "v_unit", "v_total"},  # números en formato BR
    ],
}
"""
import base64
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation

MODELO_CLAUDE = os.environ.get("ANTHROPIC_MODEL_NOTAS", "claude-haiku-5-5")
MAX_TOKENS = 8000

TIPOS_IMAGEN = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class ErrorLecturaNota(Exception):
    pass


# ── API pública ──────────────────────────────────────────────────────────────

def leer_nota(contenido: bytes, nombre_archivo: str) -> dict:
    ext = os.path.splitext(nombre_archivo or "")[1].lower()

    if ext == ".xml" or contenido.lstrip()[:5] == b"<?xml":
        return _leer_xml(contenido)

    if ext == ".pdf" or contenido[:4] == b"%PDF":
        return _leer_con_claude(contenido, "application/pdf")

    if ext in TIPOS_IMAGEN:
        return _leer_con_claude(contenido, TIPOS_IMAGEN[ext])

    raise ErrorLecturaNota("Formato no soportado. Suba un PDF, XML o imagen (JPG/PNG).")


# ── XML NF-e ─────────────────────────────────────────────────────────────────

def _leer_xml(contenido: bytes) -> dict:
    try:
        root = ET.fromstring(contenido)
    except ET.ParseError as e:
        raise ErrorLecturaNota(f"XML inválido: {e}")

    # ignorar namespaces: buscar por nombre local
    def buscar(nodo, ruta):
        actual = nodo
        for parte in ruta.split("/"):
            if actual is None:
                return None
            actual = next((h for h in actual.iter() if h.tag.split("}")[-1] == parte), None)
        return actual

    def texto(nodo, ruta, default=""):
        n = buscar(nodo, ruta)
        return (n.text or "").strip() if n is not None and n.text else default

    inf = buscar(root, "infNFe")
    if inf is None:
        raise ErrorLecturaNota("El XML no es una NF-e (no tiene infNFe).")

    chave = re.sub(r"\D", "", inf.attrib.get("Id", ""))

    fecha = texto(inf, "ide/dhEmi") or texto(inf, "ide/dEmi")
    fecha_br = ""
    if fecha:
        try:
            fecha_br = datetime.fromisoformat(fecha[:10]).strftime("%d/%m/%Y")
        except ValueError:
            pass

    items = []
    for det in (n for n in inf.iter() if n.tag.split("}")[-1] == "det"):
        items.append({
            "codigo":     texto(det, "prod/cProd"),
            "descricao":  texto(det, "prod/xProd"),
            "unidade":    texto(det, "prod/uCom").lower(),
            "quantidade": _a_br(texto(det, "prod/qCom"), 3),
            "v_unit":     _a_br(texto(det, "prod/vUnCom"), 4),
            "v_total":    _a_br(texto(det, "prod/vProd"), 2),
        })

    return {
        "proveedor":      texto(inf, "emit/xNome").upper(),
        "proveedor_cnpj": re.sub(r"\D", "", texto(inf, "emit/CNPJ") or texto(inf, "emit/CPF")),
        "numero_nfe":     texto(inf, "ide/nNF"),
        "serie":          texto(inf, "ide/serie"),
        "chave_acesso":   chave if len(chave) == 44 else "",
        "fecha_emision":  fecha_br,
        "items":          items,
    }


# ── Claude ───────────────────────────────────────────────────────────────────

_INSTRUCCIONES = """Sos un lector de notas fiscales de compra de una empresa agrícola de Brasil.
Te paso una nota (DANFE de NF-e, factura, remito o foto). Extraé los datos y devolvelos
llamando a la herramienta registrar_nota. Reglas:
- Copiá los textos tal cual figuran (descripción completa del producto, incluida la presentación,
  por ejemplo "BIG BAG 1000 KG" o "BD 20 L"). No inventes datos: si un campo no está, dejalo vacío.
- Números como números (punto decimal, sin separador de miles).
- Fecha de emisión en formato AAAA-MM-DD.
- CNPJ/CPF del EMISOR (quien vende), solo dígitos. No confundir con el destinatario.
- La clave de acceso son 44 dígitos (suele estar arriba a la derecha, con espacios): devolvela sin espacios.
- Un ítem por cada línea de producto. Ignorá las líneas de lote, safra, RENASEM o tributos
  que aparecen debajo del producto: no son productos.
- Si hay varias páginas, incluí los ítems de todas."""

_HERRAMIENTA = {
    "name": "registrar_nota",
    "description": "Registra los datos extraídos de la nota fiscal.",
    "input_schema": {
        "type": "object",
        "properties": {
            "emisor_razon_social": {"type": "string"},
            "emisor_cnpj":         {"type": "string"},
            "numero":              {"type": "string"},
            "serie":               {"type": "string"},
            "chave_acesso":        {"type": "string"},
            "fecha_emision":       {"type": "string", "description": "AAAA-MM-DD"},
            "naturaleza_operacion": {"type": "string"},
            "valor_total_nota":    {"type": "number"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "codigo":         {"type": "string"},
                        "descripcion":    {"type": "string"},
                        "unidad":         {"type": "string"},
                        "cantidad":       {"type": "number"},
                        "valor_unitario": {"type": "number"},
                        "valor_total":    {"type": "number"},
                    },
                    "required": ["descripcion", "cantidad", "valor_unitario", "valor_total"],
                },
            },
        },
        "required": ["emisor_razon_social", "numero", "fecha_emision", "items"],
    },
}


def _leer_con_claude(contenido: bytes, media_type: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ErrorLecturaNota("Falta configurar ANTHROPIC_API_KEY en el servidor.")

    try:
        import anthropic
    except ImportError:
        raise ErrorLecturaNota("Falta instalar la librería 'anthropic' (pip install anthropic).")

    datos_b64 = base64.standard_b64encode(contenido).decode("utf-8")
    bloque_archivo = {
        "type": "document" if media_type == "application/pdf" else "image",
        "source": {"type": "base64", "media_type": media_type, "data": datos_b64},
    }

    cliente = anthropic.Anthropic(api_key=api_key)
    try:
        respuesta = cliente.messages.create(
            model=MODELO_CLAUDE,
            max_tokens=MAX_TOKENS,
            system=_INSTRUCCIONES,
            tools=[_HERRAMIENTA],
            tool_choice={"type": "tool", "name": "registrar_nota"},
            messages=[{
                "role": "user",
                "content": [bloque_archivo, {"type": "text", "text": "Leé esta nota."}],
            }],
        )
    except anthropic.APIError as e:
        raise ErrorLecturaNota(f"Error de la API de Claude: {e}")

    datos = next((b.input for b in respuesta.content if b.type == "tool_use"), None)
    if not datos:
        raise ErrorLecturaNota("Claude no devolvió datos de la nota.")

    return _normalizar(datos)


def _normalizar(d: dict) -> dict:
    fecha_br = ""
    if d.get("fecha_emision"):
        try:
            fecha_br = datetime.fromisoformat(d["fecha_emision"][:10]).strftime("%d/%m/%Y")
        except ValueError:
            pass

    chave = re.sub(r"\D", "", d.get("chave_acesso") or "")

    items = [{
        "codigo":     (i.get("codigo") or "").strip(),
        "descricao":  (i.get("descripcion") or "").strip(),
        "unidade":    (i.get("unidad") or "").strip().lower(),
        "quantidade": _a_br(i.get("cantidad"), 3),
        "v_unit":     _a_br(i.get("valor_unitario"), 4),
        "v_total":    _a_br(i.get("valor_total"), 2),
    } for i in d.get("items") or []]

    return {
        "proveedor":      (d.get("emisor_razon_social") or "").strip().upper(),
        "proveedor_cnpj": re.sub(r"\D", "", d.get("emisor_cnpj") or ""),
        "numero_nfe":     re.sub(r"\D", "", d.get("numero") or "").lstrip("0") or (d.get("numero") or ""),
        "serie":          (d.get("serie") or "").strip(),
        "chave_acesso":   chave if len(chave) == 44 else "",
        "fecha_emision":  fecha_br,
        "items":          items,
    }


# ── helpers ──────────────────────────────────────────────────────────────────

def _a_br(valor, decimales: int) -> str:
    """1234.5 -> '1.234,500' (formato que espera la pantalla de revisión)."""
    if valor in (None, ""):
        return ""
    try:
        num = Decimal(str(valor))
    except InvalidOperation:
        return ""
    texto = f"{num:,.{decimales}f}"          # 1,234.500
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")
