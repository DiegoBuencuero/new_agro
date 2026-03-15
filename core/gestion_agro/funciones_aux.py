from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import FaseAgricola, ActividadProductiva


def validar_fecha_dentro_del_ciclo(ciclo, fecha):
    if fecha < ciclo.fecha_inicio:
        raise ValidationError(_("La fecha de la actividad no puede ser anterior al inicio del ciclo."))

    if ciclo.fecha_fin and fecha > ciclo.fecha_fin:
        raise ValidationError(_("La fecha de la actividad no puede ser posterior al fin del ciclo."))


def obtener_fase_abierta(ciclo):
    fases_abiertas = FaseAgricola.objects.filter(ciclo=ciclo, estado="abierto")

    if fases_abiertas.count() > 1:
        raise ValidationError(_("El ciclo tiene más de una fase abierta. Revise la configuración."))

    return fases_abiertas.first()


def determinar_tipo_fase_por_subtipo(subtipo):
    if not subtipo:
        return None

    if subtipo.codigo == "COB":
        return "COB"

    if subtipo.codigo == "PRI":
        return "PRI"

    return None


def actividad_puede_abrir_fase(tipo_actividad):
    return tipo_actividad.tiene_caracteristica("AF")


def actividad_debe_cerrar_fase(fase, tipo_actividad, subtipo):
    if not fase:
        return False

    if tipo_actividad.tiene_caracteristica("CF"):
        return True

    if fase.tipo == "COB":
        if tipo_actividad.nombre.lower() == "aplicación" or tipo_actividad.nombre.lower() == "aplicacion":
            if subtipo and subtipo.codigo == "DES":
                return True

    return False


def crear_fase_si_corresponde(ciclo, tipo_actividad, subtipo, fecha):
    tipo_fase = None
    nombre_tipo = tipo_actividad.nombre.strip().lower()

    if nombre_tipo == "siembra":
        tipo_fase = determinar_tipo_fase_por_subtipo(subtipo)

    elif nombre_tipo in ["aplicación", "aplicacion"]:
        if subtipo and subtipo.codigo == "DES":
            tipo_fase = "PRI"

    if not tipo_fase:
        raise ValidationError(_("No se pudo determinar el tipo de fase a abrir."))

    fase = FaseAgricola.objects.create(
        ciclo=ciclo,
        tipo=tipo_fase,
        fecha_inicio=fecha,
        estado="abierto"
    )

    return fase


def validar_actividad_inicial_de_fase(fase, tipo_actividad):
    cantidad_actividades = ActividadProductiva.objects.filter(fase=fase).count()

    if cantidad_actividades == 0:
        if tipo_actividad.nombre.lower() == "cosecha":
            raise ValidationError(_("No se puede iniciar una fase con una cosecha."))


def validar_siembra_unica_por_fase(fase, tipo_actividad, subtipo):
    if tipo_actividad.nombre.lower() != "siembra":
        return

    siembras_existentes = ActividadProductiva.objects.filter(
        fase=fase,
        tipo__nombre__iexact="siembra"
    )

    if not siembras_existentes.exists():
        return

    if subtipo and subtipo.codigo == "RES":
        return

    raise ValidationError(_("La fase ya tiene una siembra registrada. Solo se permite otra siembra si es una resiembra."))


def validar_fecha_dentro_de_la_fase(fase, fecha):
    if not fase:
        return

    if fecha < fase.fecha_inicio:
        raise ValidationError(_("La fecha de la actividad no puede ser anterior al inicio de la fase."))

    if fase.fecha_fin and fecha > fase.fecha_fin:
        raise ValidationError(_("La fecha de la actividad no puede ser posterior al fin de la fase."))


def validar_reglas_basicas_actividad(ciclo, fase, tipo_actividad, subtipo, fecha):
    validar_fecha_dentro_del_ciclo(ciclo, fecha)

    if fase:
        validar_fecha_dentro_de_la_fase(fase, fecha)
        validar_actividad_inicial_de_fase(fase, tipo_actividad)
        validar_siembra_unica_por_fase(fase, tipo_actividad, subtipo)


def cerrar_fase(fase, fecha):
    fase.estado = "cerrado"
    fase.fecha_fin = fecha
    fase.save()