from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from gestion_agro.models import (
    MovimientoStock,
    FaseAgricola,
    ActividadProductiva,
)

def obtener_reglas_de_fase(tipo, subtipo):
    # de donde saco si abre o cierra fase
    if subtipo:
        return subtipo.puede_abrir_fase, subtipo.puede_cerrar_fase

    return tipo.abre_fase, tipo.cierra_fase


def validar_reglas_generales(ciclo, fase, tipo, subtipo, fecha, puede_abrir_fase):
    # validaciones base del flujo
    if fecha < ciclo.fecha_inicio:
        return False, _("La fecha es anterior al inicio del ciclo.")

    if tipo.requiere_subtipo and not subtipo:
        return False, _("Debe seleccionar un subtipo.")

    if not fase and not puede_abrir_fase:
        return False, _("No hay fase abierta y esta actividad no puede abrir una.")

    if fase and fase.estado == "abierto" and fecha < fase.fecha_inicio:
        return False, _("La fecha es menor al inicio de la fase.")

    if fase and fase.estado == "cerrado" and not puede_abrir_fase:
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
    if tipo.nombre.lower() != "siembra" or not fase:
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


def crear_fase_si_corresponde(ciclo, fase, fecha, puede_abrir_fase):
    # si la actividad abre fase y hace falta, la creo
    inicio_fase = False

    if puede_abrir_fase and (not fase or fase.estado == "cerrado"):
        fase = FaseAgricola.objects.create(
            ciclo=ciclo,
            tipo="PRI",
            fecha_inicio=fecha,
            estado="abierto",
        )
        inicio_fase = True

    return fase, inicio_fase


def cerrar_fase_si_corresponde(fase, fecha, puede_cerrar_fase):
    # si corresponde, cierro la fase
    if puede_cerrar_fase and fase and fase.estado == "abierto":
        fase.fecha_fin = fecha
        fase.estado = "cerrado"
        fase.save()


def guardar_insumos_y_stock(actividad, tipo, insumo_formset):
    # guarda insumos y descuenta stock
    if not tipo.requiere_insumo:
        return

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
    actividad_form,
    insumo_formset,
    vistoria_form=None,
    cosecha_form=None,
):
    tipo = actividad_form.cleaned_data["tipo"]
    subtipo = actividad_form.cleaned_data.get("subtipo")
    fecha = actividad_form.cleaned_data["fecha"]

    # 1. reglas de fase
    puede_abrir_fase, puede_cerrar_fase = obtener_reglas_de_fase(tipo, subtipo)

    # 2. validaciones generales
    ok, msg = validar_reglas_generales(ciclo, fase, tipo, subtipo, fecha, puede_abrir_fase)
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
    fase, inicio_fase = crear_fase_si_corresponde(ciclo, fase, fecha, puede_abrir_fase)

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

    # 10. extras
    guardar_insumos_y_stock(actividad, tipo, insumo_formset)
    guardar_monitoreo(actividad, tipo, vistoria_form)
    guardar_cosecha(actividad, tipo, cosecha_form)

    # 11. cerrar fase
    cerrar_fase_si_corresponde(fase, fecha, puede_cerrar_fase)

    return True, {
        "actividad": actividad,
        "inicio_fase": inicio_fase,
    }