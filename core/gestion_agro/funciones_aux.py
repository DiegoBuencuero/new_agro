from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from gestion_agro.models import (
    MovimientoStock,
    FaseAgricola,
    ActividadProductiva,
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
    superficie,
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

    tiene_insumos = False

    # valores base desde configuración
    v_mo, v_mq, c_mo_unit, c_mq_unit = obtener_valores_costos(tipo, subtipo, empresa)

    # damos prioridad a los vores ingresados por el usuario
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
        if not insumo.producto:
            continue

        tiene_insumos = True

        cantidad = insumo.dosis * superficie
        costo = cantidad * insumo.producto.precio

        costo_insumos += costo

    # mano de obra
    if v_mo is not None and c_mo_unit is not None:
        horas_hombre = v_mo * superficie
        costo_mo = horas_hombre * c_mo_unit

    # maquina
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

def guardar_insumos_y_stock(actividad, tipo, insumo_formset):
    # guarda insumos y descuenta stock
    if not tipo.requiere_insumo:
        return []

    insumo_formset.instance = actividad
    insumos = insumo_formset.save()

    for insumo in insumos:
        if not insumo.producto:
            continue

        MovimientoStock.objects.create(
            producto=insumo.producto,
            tipo="SALIDA",
            cantidad=insumo.dosis,
            um=insumo.um,
            fecha=timezone.now(),
            actividad=actividad,
            precio_unitario=insumo.producto.precio,
        )

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
    insumos = guardar_insumos_y_stock(actividad, tipo, insumo_formset)

    # 11. calcular costos
    costo_insumos, horas_hombre, costo_mo, horas_maquina, costo_mq, total = calcular_costos_actividad(
        tipo,
        subtipo,
        empresa,
        ciclo.superficie_ha,
        insumos,
    )

    # 12. guardar horas y valores en actividad
    v_mo, v_mq, c_mo_unit, c_mq_unit = obtener_valores_costos(tipo, subtipo, empresa)

    actividad.cantidad_hombre = horas_hombre
    actividad.valor_hombre = c_mo_unit or 0
    actividad.cantidad_h_maq = horas_maquina
    actividad.valor_h_maq = c_mq_unit or 0
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