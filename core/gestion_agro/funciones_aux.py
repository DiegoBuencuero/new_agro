from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from typing import Any, Dict, List, Optional, Tuple
from django.http import JsonResponse
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from datetime import datetime
from agro.models import ConversionUM, Unidad
from gestion_agro.models import ( MovimientoStock, FaseAgricola, ActividadProductiva,
                                   ActividadInsumo, CamposInspeccion,
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
    if v_mo is None:
        v_mo = tipo.valor_x_ha_mo
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
    if not tipo.requiere_insumo:
        return True, None

    if not insumo_formset.is_valid():
        return False, _("Hay errores en los insumos.")

    hay_insumos = False
    semillas_count = 0

    for formulario in insumo_formset:
        if not hasattr(formulario, "cleaned_data"):
            continue
        cd = formulario.cleaned_data
        if not cd or cd.get("DELETE", False):
            continue
        hay_insumos = True
        producto = cd.get("producto")
        if producto and hasattr(producto, "categoria") and producto.categoria.es_semilla:
            semillas_count += 1

    if not hay_insumos:
        return False, _("Debe cargar al menos un insumo.")

    if tipo.nombre_es.lower() == "siembra" and semillas_count > 1:
        return False, _("Solo se permite una semilla por siembra.")

    return True, None

def validar_inspeccion(tipo, inspeccion_form):
    if not tipo.requiere_inspeccion:
        return True, None

    if not inspeccion_form or not inspeccion_form.is_valid():
        return False, _("Hay errores en los datos de inspección.")

    return True, None


def validar_monitoreo(tipo, vistoria_form):
    # valida vistoria si aplica
    if not tipo.requiere_vist:
        return True, None

    if not vistoria_form or not vistoria_form.is_valid():
        return False, _("Hay errores en los datos de monitoreo.")

    return True, None

def validar_cosecha(ciclo, tipo, fecha, cosecha_form):
    if not tipo.requiere_cosecha:
        return True, None

    if not cosecha_form or not cosecha_form.is_valid():
        errores = []
        if cosecha_form:
            for field, errs in cosecha_form.errors.items():
                for e in errs:
                    errores.append(f"{field}: {e}")
        msg = " | ".join(errores) if errores else _("Hay errores en los datos de cosecha.")
        return False, msg

    rendimiento = cosecha_form.cleaned_data.get("rendimiento")
    if not rendimiento or rendimiento <= 0:
        return False, _("El rendimiento es obligatorio y debe ser mayor a 0.")

    um_id = cosecha_form.cleaned_data.get("um")
    if not um_id:
        return False, _("Debe seleccionar la unidad de medida del rendimiento.")

    existe_siembra = ActividadProductiva.objects.filter(
        fase__ciclo=ciclo,
        tipo__nombre_es__iexact="Siembra",
        fecha__lte=fecha,
    ).exists()

    if not existe_siembra:
        return False, _("No se puede registrar cosecha sin una siembra previa.")

    return True, None

def validar_reglas_siembra(fase, tipo, subtipo):
    # reglas propias de siembra
    if tipo.nombre_es.lower() != "siembra":
        return True, None

    if not subtipo:
        return False, _("La siembra requiere seleccionar un subtipo (Cultivo principal, Cobertura, etc.).")

    nombre_subtipo = subtipo.nombre_es.lower()

    existe_principal = ActividadProductiva.objects.filter(
        fase=fase,
        tipo=tipo,
        subtipo__nombre_es__iexact="Cultivo principal",
    ).exists()

    existe_cobertura = ActividadProductiva.objects.filter(
        fase=fase,
        tipo=tipo,
        subtipo__nombre_es__iexact="Cobertura",
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
    if tipo.nombre_es.lower() != "aplicación" or not fase:
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

def obtener_capas_stock(producto, unidad, metodo="FIFO"):
    entradas = list(
        MovimientoStock.objects
        .filter(
            producto=producto,
            tipo=MovimientoStock.Tipo.ENTRADA,
        )
        .order_by("fecha", "id")
        .values("id", "fecha", "cantidad", "um", "precio_unitario")
    )

    salidas = list(
        MovimientoStock.objects
        .filter(
            producto=producto,
            tipo=MovimientoStock.Tipo.SALIDA,
        )
        .order_by("fecha", "id")
        .values("id", "fecha", "cantidad", "um")
    )

    capas = []
    for e in entradas:
        unidad_origen = Unidad.objects.get(id=e["um"])
        capas.append({
            "movimiento_id":       e["id"],
            "fecha":               e["fecha"],
            "precio_unitario":     convertir_unidad_precio(e["precio_unitario"], unidad_origen, unidad),
            "cantidad_original":   convertir_unidad(e["cantidad"], unidad_origen, unidad),
            "cantidad_disponible": convertir_unidad(e["cantidad"], unidad_origen, unidad),
        })

    for s in salidas:
        unidad_mov = Unidad.objects.get(id=s["um"])
        pendiente = convertir_unidad(s["cantidad"], unidad_mov, unidad)

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

def calcular_costo_salida(producto, cantidad_salida, unidad, metodo="FIFO", precio_faltante=None):
    cantidad_salida = Decimal(cantidad_salida)
    capas = obtener_capas_stock(producto, unidad, metodo=metodo)

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
        # precio_faltante solo llega si la empresa permite aplicar insumos sin stock
        if precio_faltante is None:
            raise ValueError("Stock insuficiente para realizar la salida.")
        costo_parcial = pendiente * precio_faltante
        detalle.append({
            "movimiento_entrada_id": None,
            "cantidad": pendiente,
            "precio_unitario": precio_faltante,
            "costo_parcial": costo_parcial,
        })
        costo_total += costo_parcial
        pendiente = Decimal("0")

    precio_promedio = (
        costo_total / cantidad_salida if cantidad_salida > 0 else Decimal("0")
    )

    return {
        "costo_total": costo_total,
        "precio_promedio": precio_promedio,
        "detalle": detalle,
    }

def guardar_insumos_y_stock(actividad, tipo, insumo_formset, empresa):
    if not tipo.requiere_insumo:
        return []

    with transaction.atomic():
        insumo_formset.instance = actividad
        insumos = insumo_formset.save()

        superficie = actividad.fase.ciclo.superficie_ha

        if empresa.calculo_costo == "F":
            metodo = "FIFO"
        elif empresa.calculo_costo == "L":
            metodo = "LIFO"
        else:
            metodo = "FIFO"

        # la salida va con la fecha de la actividad, no con la de carga
        fecha_mov = timezone.make_aware(
            datetime.combine(actividad.fecha, datetime.min.time())
        )

        for insumo in insumos:
            if not insumo.producto:
                continue

            # depósito: el del producto o, si no tiene, el de insumos de la empresa
            deposito = insumo.producto.deposito_default or empresa.deposito_insumos_default
            if deposito is None:
                raise ValueError(
                    _("El producto %(prod)s no tiene depósito asignado y la empresa no tiene "
                      "depósito de insumos por defecto. Configúrelo antes de continuar.")
                    % {"prod": insumo.producto}
                )

            cantidad = insumo.dosis * superficie
            precio_faltante = None
            if empresa.permite_sin_stock:
                precio_faltante = convertir_unidad_precio(
                    insumo.producto.precio or Decimal("0"), insumo.producto.unidad_base, insumo.um,
                )
                if precio_faltante is None:
                    raise ValueError(
                        _("Falta conversión de unidad: %(origen)s → %(destino)s. Configurala en el sistema antes de continuar.")
                        % {"origen": insumo.producto.unidad_base, "destino": insumo.um}
                    )

            algo = calcular_costo_salida(insumo.producto, cantidad, insumo.um, metodo=metodo, precio_faltante=precio_faltante)
            MovimientoStock.objects.create(
                producto=insumo.producto,
                tipo="SALIDA",
                cantidad=cantidad,
                um=insumo.um,
                fecha=fecha_mov,
                actividad_item=insumo,
                actividad=actividad,
                deposito_origen=deposito,
                precio_unitario=algo["precio_promedio"],
            )
            insumo.cantidad_real = cantidad
            insumo.costo_total   = algo["costo_total"]
            insumo.costo_ha      = algo["costo_total"] / superficie if superficie else Decimal("0")
            try:
                pmg = insumo.producto.datos_semilla.variedad.pmg
                if pmg and pmg > 0:
                    insumo.densidad_siembra = round(insumo.dosis * Decimal("1000000") / pmg)
            except Exception:
                pass
            insumo.save()

    return insumos

def guardar_monitoreo(actividad, tipo, vistoria_form):
    # guarda datos de monitoreo
    if not tipo.requiere_vist or not vistoria_form:
        return

    vistoria = vistoria_form.save(commit=False)
    vistoria.actividad = actividad
    vistoria.save()

def guardar_inspeccion(actividad, tipo, inspeccion_form):
    if not tipo.requiere_inspeccion or not inspeccion_form:
        return None

    inspeccion = inspeccion_form.save(commit=False)
    inspeccion.actividad = actividad
    inspeccion.save()
    return inspeccion

def guardar_cosecha(actividad, tipo, cosecha_form):
    if not tipo.requiere_cosecha or not cosecha_form:
        return None

    cosecha = cosecha_form.save(commit=False)
    cosecha.actividad = actividad
    cosecha.save()
    return cosecha
    
def registrar_actividad_aux(
    ciclo,
    fase,
    empresa,
    actividad_form,
    insumo_formset,
    vistoria_form=None,
    cosecha_form=None,
    inspeccion_form=None,
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

    # 4b. inspección semilla
    ok, msg = validar_inspeccion(tipo, inspeccion_form)
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
    try:
        actividad = actividad_form.save(commit=False)
        actividad.fase = fase
        actividad.save()

        # 10. guardar insumos y stock
        insumos = guardar_insumos_y_stock(actividad, tipo, insumo_formset, empresa)
    except (ValueError, TypeError) as e:
        return False, str(e)

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
    costo_insumos_real = sum(i.costo_total or Decimal("0") for i in (insumos or []))
    actividad.total_mo  = horas_hombre  * (c_mo_unit  or Decimal("0"))
    actividad.total_maq = horas_maquina * (c_mq_unit  or Decimal("0"))
    actividad.total     = costo_insumos_real + actividad.total_mo + actividad.total_maq
    actividad.save()

    # 13. guardar extras
    guardar_monitoreo(actividad, tipo, vistoria_form)
    guardar_inspeccion(actividad, tipo, inspeccion_form)
    cosecha_obj = guardar_cosecha(actividad, tipo, cosecha_form)

    from datetime import datetime
    import datetime as dt

    # 13b. movimientos de stock por cosecha
    # Tres orígenes claros en MovimientoStock:
    #   factura_item IS NOT NULL  → COMPRA (insumo)
    #   cosecha      IS NOT NULL  → PRODUCCIÓN PROPIA (semilla o consumo de cosecha)
    #   actividad_item IS NOT NULL → CONSUMO en actividad
    if tipo.requiere_cosecha and ciclo.producto_final:
        rendimiento      = cosecha_form.cleaned_data.get("rendimiento")
        um_id            = cosecha_form.cleaned_data.get("um")
        deposito_semilla = cosecha_form.cleaned_data.get("deposito_semilla")
        deposito_consumo = cosecha_form.cleaned_data.get("deposito_consumo") or cosecha_form.cleaned_data.get("deposito_destino")

        dep_consumo_default = (
            ciclo.producto_final.deposito_default
            or empresa.deposito_producto_final_default
        )
        if not deposito_consumo:
            deposito_consumo = dep_consumo_default
        if not deposito_semilla:
            deposito_semilla = dep_consumo_default

        if rendimiento:
            unidad_base = ciclo.producto_final.unidad_base
            factor = Decimal("1")
            if um_id and um_id != unidad_base.id:
                try:
                    conv = ConversionUM.objects.get(um_origen_id=um_id, um_destino=unidad_base)
                    factor = conv.factor
                except ConversionUM.DoesNotExist:
                    pass

            cantidad_total = rendimiento * ciclo.superficie_ha * factor
            fecha_cosecha  = datetime.combine(actividad.fecha, dt.time.min)

            # Desdoblamiento si hay inspección aprobada O si el producto es semilla
            inspeccion = CamposInspeccion.objects.filter(
                actividad__fase__ciclo=ciclo,
                resultado=CamposInspeccion.Resultado.APROBADO,
            ).select_related("um").order_by("-actividad__fecha", "-id").first()

            es_semilla_ciclo = bool(inspeccion) or bool(
                ciclo.producto_final.categoria and
                ciclo.producto_final.categoria.es_semilla
            )

            producto_semilla = (
                ciclo.cultivo.productos_finales.filter(categoria__es_semilla=True).first()
                or ciclo.producto_final
            )

            # Calcular split semilla / consumo
            if es_semilla_ciclo and inspeccion and inspeccion.cant_semilla_mult_ha:
                um_insp     = inspeccion.um
                factor_insp = Decimal("1")
                if um_insp and um_insp.requiere_pmg:
                    pmg = None
                    try:
                        insumo_s = ActividadInsumo.objects.filter(
                            actividad__fase__ciclo=ciclo,
                            actividad__tipo__nombre_es__iexact="siembra",
                            producto__categoria__es_semilla=True,
                        ).select_related("producto__datos_semilla__variedad").first()
                        pmg = insumo_s.producto.datos_semilla.variedad.pmg
                    except Exception:
                        pass
                    kg_semilla = (
                        min(inspeccion.cant_semilla_mult_ha * ciclo.superficie_ha * pmg / Decimal("1000000"), cantidad_total)
                        if pmg and pmg > 0 else Decimal("0")
                    )
                else:
                    if um_insp and um_insp != unidad_base:
                        try:
                            c = ConversionUM.objects.get(um_origen=um_insp, um_destino=unidad_base)
                            factor_insp = c.factor
                        except ConversionUM.DoesNotExist:
                            pass
                    kg_semilla = min(
                        inspeccion.cant_semilla_mult_ha * ciclo.superficie_ha * factor_insp,
                        cantidad_total,
                    )
                kg_consumo = cantidad_total - kg_semilla
            else:
                kg_semilla = Decimal("0")
                kg_consumo = cantidad_total

            with transaction.atomic():
                if kg_semilla > 0:
                    MovimientoStock.objects.create(
                        producto=producto_semilla,
                        tipo=MovimientoStock.Tipo.ENTRADA,
                        cantidad=kg_semilla,
                        um=unidad_base,
                        fecha=fecha_cosecha,
                        actividad=actividad,
                        cosecha=cosecha_obj,
                        destino="M",
                        actividad_item=None,
                        factura_item=None,
                        precio_unitario=Decimal("0"),
                        deposito_destino=deposito_semilla,
                    )
                if kg_consumo > 0:
                    MovimientoStock.objects.create(
                        producto=ciclo.producto_final,
                        tipo=MovimientoStock.Tipo.ENTRADA,
                        cantidad=kg_consumo,
                        um=unidad_base,
                        fecha=fecha_cosecha,
                        actividad=actividad,
                        cosecha=cosecha_obj,
                        destino="C",
                        actividad_item=None,
                        factura_item=None,
                        precio_unitario=Decimal("0"),
                        deposito_destino=deposito_consumo,
                    )

    # 14. cerrar fase
    cerrar_fase_si_corresponde(fase, fecha, cierra_fase)

    return True, {
        "actividad": actividad,
        "inicio_fase": inicio_fase,
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

#---------------- Ayuda unidades-----------
def convertir_unidad(cantidad, unidad_origen, unidad_destino):
    if unidad_origen == unidad_destino:
        return cantidad
    convercion = ConversionUM.objects.filter(um_origen=unidad_origen, um_destino=unidad_destino).first()
    if convercion:
        return cantidad * convercion.factor
    raise ValueError(
        _("Falta conversión de unidad: %(origen)s → %(destino)s. Configurala en el sistema antes de continuar.") % {
            "origen":  unidad_origen,
            "destino": unidad_destino,
        }
    )
    
def convertir_unidad_precio(precio, unidad_origen, unidad_destino):

    if unidad_origen == unidad_destino:
        return precio

    convercion = ConversionUM.objects.filter(um_origen=unidad_origen, um_destino=unidad_destino).first()
    
    if convercion:
        return precio / convercion.factor
    else:           
        return None
    