from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from .funciones_aux import (  obtener_fase_abierta, validar_reglas_basicas_actividad,   crear_fase_si_corresponde,
                            actividad_debe_cerrar_fase,
                            )
from gestion_agro.forms import ( CampoForm, CampanaForm, CicloForm, CicloFiltroForm,
                                ActividadProductivaForm, ActividadInsumoForm, ActividadInsumoFormSet)
from gestion_agro.models import ( Campo, Campana, CicloAgricola, FaseAgricola, SubTipoActividad,
                                ActividadProductiva, Producto, TipoActividad, TipoActividadCategoriaProducto,
                                CamposVistoria, CamposCosecha )


@login_required
def vista_crear_campo(request):
    empresa = request.user.profile.empresa

    campos = Campo.objects.filter(empresa=empresa)

    if request.method == "POST":
        form = CampoForm(request.POST, request.FILES)
        if form.is_valid():
            campo = form.save(commit=False)
            campo.empresa = empresa
            campo.save()

            messages.success(request, _("Campo creado correctamente"))
            return redirect("vista_crear_campo")
    else:
        form = CampoForm()

    return render(
        request,
        "vista_crear_campo.html",
        {
            "form": form,
            "campos": campos,
            "empresa": empresa,
        },
    )

@login_required
def vista_editar_campo(request, id_campo):
    campos = Campo.objects.filter(empresa = request.user.profile.empresa)
    try:
        campo = Campo.objects.get(id = id_campo)
    except:
        return redirect('vista_crear_campo')
    empresa = request.user.profile.empresa
    if campo.empresa ==empresa:
        if request.method == 'POST':
            form = CampoForm(request.POST, request.FILES, instance = campo)
            if form.is_valid():
                campo = form.save(commit=False)
                if request.POST.get('borrar') == '':
                    campo.delete()
                else:
                    campo.empresa = empresa
                    campo.save()
                return redirect('vista_crear_campo')
            else:
                messages.error(request, form.errors.as_data() )
        else:
            form = CampoForm(instance = campo)
        return render(request, 'vista_crear_campo.html', {'form': form, 'campos': campos, 'empresa': empresa, 'modificacion': 'S'})
    else:
        return redirect('vista_crear_campo')

@login_required
def vista_crear_campana(request):
    empresa = request.user.profile.empresa
    campanas = Campana.objects.filter(empresa=empresa)
    print(empresa)

    if request.method == "POST":
        form = CampanaForm(request.POST)
        if form.is_valid():
            campana = form.save(commit=False)
            campana.empresa = empresa

            if Campana.objects.filter(
                empresa=empresa,
                nombre=f"{campana.fecha_desde.year}/{campana.fecha_desde.year + 1}"
            ).exists():
                messages.error(request, _("Ya existe una campaña para ese período"))
                return redirect("vista_crear_campana")

            campana.save()
            messages.success(request, _("Campaña creada correctamente"))
            return redirect("vista_crear_campana")
    else:
        form = CampanaForm()

    campanas = Campana.objects.filter(empresa=empresa)

    return render(
        request,
        "vista_crear_campana.html",
        {
            "form": form,
            "campanas": campanas,
            "empresa": empresa,
        },
    )

@login_required
def vista_editar_campana(request, id_campana):
    campanas = Campana.objects.filter(empresa = request.user.profile.empresa)
    try:
        camp = Campana.objects.get(id = id_campana)
    except:
        return redirect('vista_campana')
    empresa = request.user.profile.empresa
    if camp.empresa == empresa:
        if request.method == 'POST':
            form = CampanaForm(request.POST, instance = camp)
            if form.is_valid():
                campana = form.save(commit=False)
                if request.POST.get('borrar') == '':
                    campana.delete()
                else:
                    campana.save()
                return redirect('vista_campana')
        else:
            form = CampanaForm(instance = camp)
        return render(request, 'vista_campana.html', {'form': form, 'empresa': empresa, 'campanas':campanas, 'modificacion': 'S'})
    else:
        return redirect('vista_campana')
   
@login_required
def vista_lista_ciclos(request):
    empresa = request.user.profile.empresa

    ciclos = (
        CicloAgricola.objects.filter(
            campo__empresa=empresa,
            activa=True
        )
        .select_related("campo", "campana", "cultivo")
        .order_by("-fecha_inicio")
    )

    form = CicloFiltroForm(empresa=empresa)

    context = {
        "ciclos": ciclos,
        "form": form,
        "empresa": empresa,
    }

    return render(request, "vista_lista_ciclos.html", context)

@login_required
def ajax_get_ciclos_data(request):
    empresa = request.user.profile.empresa

    ciclos = CicloAgricola.objects.filter(
        campo__empresa=empresa
    ).select_related(
        "campo", "campana", "cultivo"
    ).order_by("-fecha_inicio")

    campana_id = request.GET.get("campana")
    campo_id = request.GET.get("campo")
    cultivo_id = request.GET.get("cultivo")
    estado = request.GET.get("estado")

    if campana_id:
        ciclos = ciclos.filter(campana_id=campana_id)

    if campo_id:
        ciclos = ciclos.filter(campo_id=campo_id)

    if cultivo_id:
        ciclos = ciclos.filter(cultivo_id=cultivo_id)

    if estado == "activo":
        ciclos = ciclos.filter(activa=True)
    elif estado == "cerrado":
        ciclos = ciclos.filter(activa=False)

    lista_data = []

    for ciclo in ciclos:
        item = {
            "id": ciclo.id,
            "campo": ciclo.campo.nombre if ciclo.campo else "",
            "campana": str(ciclo.campana) if ciclo.campana else "",
            "nombre_lote": ciclo.nombre_lote if ciclo.nombre_lote else "",
            "cultivo": str(ciclo.cultivo) if ciclo.cultivo else "",
            "superficie_ha": str(ciclo.superficie_ha) if ciclo.superficie_ha is not None else "",
            "fecha_inicio": ciclo.fecha_inicio.strftime("%d/%m/%Y") if ciclo.fecha_inicio else "",
            "estado": "cerrado" if ciclo.fecha_fin else "activo",
            "estado_label": "Cerrado" if ciclo.fecha_fin else "Activo",
            "detalle_url": reverse("vista_detalle_ciclo", args=[ciclo.id])
        }
        lista_data.append(item)

    return JsonResponse({
        "response": 1,
        "data": lista_data
    })

@login_required
def vista_crear_ciclo(request):
    empresa = request.user.profile.empresa

    if not empresa:
        messages.error(request, _("El usuario no tiene una empresa asociada."))
        return redirect("index")

    if request.method == "POST":
        form = CicloForm(request.POST, empresa=empresa)

        if form.is_valid():
            ciclo = form.save(commit=False)

            campo = ciclo.campo
            campana = ciclo.campana

            numero_lote = (
                CicloAgricola.objects
                .filter(campo=campo, campana=campana)
                .count() + 1
            )

            ciclo.nombre_lote = _("Lote-%(numero)s") % {
                "numero": numero_lote
            }
            ciclo.activa = True
            ciclo.save()

            messages.success(
                request,
                _("Ciclo creado correctamente. Ahora podés registrar actividades.")
            )
            return redirect("vista_lista_ciclos")
    else:
        form = CicloForm(empresa=empresa)

    context = {
        "form": form,
        "empresa": empresa,
    }

    return render(request, "vista_crear_ciclo.html", context)

@login_required
def vista_detalle_ciclo(request, id_ciclo):
    empresa = request.user.profile.empresa
    ciclo = CicloAgricola.objects.filter(campo__empresa=empresa, id=id_ciclo).first()
    fases = FaseAgricola.objects.filter(ciclo=ciclo)
    actividades = ActividadProductiva.objects.filter(fase__ciclo=ciclo).order_by("fecha")

    context = {
        "ciclo": ciclo,
        "fases": fases,
        "actividades": actividades,
    }


    return render(request, "vista_detalle_ciclo.html", context)

def vista_editar_ciclo():
    pass

@login_required
def ajax_subtipos_tipo_actividad(request):
    tipo_id = request.GET.get("tipo_id")

    if not tipo_id:
        return JsonResponse({
            "ok": False,
            "subtipos": []
        })

    subtipos = SubTipoActividad.objects.filter( tipo_actividad_id=tipo_id, activo=True).order_by("nombre")

    data = [
        {
            "id": subtipo.id,
            "nombre": subtipo.nombre
        }
        for subtipo in subtipos
    ]

    return JsonResponse({"ok": True, "subtipos": data })

@login_required
def vista_agregar_actividad(request, id_ciclo):
    empresa = request.user.profile.empresa
    ciclo = CicloAgricola.objects.filter(
        id=id_ciclo,
        campo__empresa=empresa
    ).first()

    if not ciclo:
        messages.error(request, "El ciclo no existe.")
        return redirect("vista_lista_ciclos")

    if not ciclo.activa:
        messages.error(request, "El ciclo está cerrado.")
        return redirect("vista_detalle_ciclo", id_ciclo=ciclo.id)

    fase = (
        FaseAgricola.objects
        .filter(ciclo=ciclo)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    if request.method == "POST":
        actividad_form = ActividadProductivaForm(request.POST)
        insumo_formset = ActividadInsumoFormSet(request.POST, prefix="insumos")

        if actividad_form.is_valid():
            tipo = actividad_form.cleaned_data["tipo"]
            subtipo = actividad_form.cleaned_data.get("subtipo")
            fecha = actividad_form.cleaned_data["fecha"]

            requiere_subtipo = tipo.requiere_subtipo
            requiere_insumo = tipo.requiere_insumo
            abre_fase = tipo.abre_fase
            cierra_fase = tipo.cierra_fase

            context = {
                "ciclo": ciclo,
                "actividad_form": actividad_form,
                "insumo_formset": insumo_formset,
            }

            if fecha < ciclo.fecha_inicio:
                messages.error(request, "La fecha no puede ser anterior al inicio del ciclo.")
                return render(request, "vista_agregar_actividad.html", context)

            if requiere_subtipo and not subtipo:
                messages.error(request, "Este tipo de actividad requiere subtipo.")
                return render(request, "vista_agregar_actividad.html", context)

            if subtipo and subtipo.tipo_actividad_id != tipo.id:
                messages.error(request, "El subtipo no corresponde al tipo seleccionado.")
                return render(request, "vista_agregar_actividad.html", context)

            # REGLA DE FASE
            # 1) si no existe ninguna fase, solo seguimos si la actividad abre fase
            if not fase:
                if not abre_fase:
                    messages.error(request, "Todavía no existe ninguna fase. Debes registrar una actividad que abra fase.")
                    return render(request, "vista_agregar_actividad.html", context)

            # 2) si existe una fase abierta, trabajamos sobre esa
            elif fase.estado == "abierto":
                if fecha < fase.fecha_inicio:
                    messages.error(request, "La fecha no puede ser anterior al inicio de la fase abierta.")
                    return render(request, "vista_agregar_actividad.html", context)

                if abre_fase:
                    messages.error(request, "La última fase ya está abierta. No puedes abrir otra.")
                    return render(request, "vista_agregar_actividad.html", context)

            # 3) si la última fase está cerrada, solo una actividad que abre fase puede crear una nueva
            elif fase.estado == "cerrado":
                if not abre_fase:
                    messages.error(request, "La última fase está cerrada. Debes usar una actividad que abra una nueva fase.")
                    return render(request, "vista_agregar_actividad.html", context)

            if requiere_insumo:
                if not insumo_formset.is_valid():
                    messages.error(request, "Revisa los insumos.")
                    return render(request, "vista_agregar_actividad.html", context)

                hay_insumos = False
                for form in insumo_formset:
                    if hasattr(form, "cleaned_data"):
                        if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                            hay_insumos = True
                            break

                if not hay_insumos:
                    messages.error(request, "Debes cargar al menos un insumo.")
                    return render(request, "vista_agregar_actividad.html", context)

            try:
                # Si no hay fase o la última está cerrada, y esta actividad abre fase, creo nueva
                if abre_fase and (not fase or fase.estado == "cerrado"):
                    fase = FaseAgricola.objects.create(
                        ciclo=ciclo,
                        tipo="PRI",
                        fecha_inicio=fecha,
                        estado="abierto"
                    )

                actividad = actividad_form.save(commit=False)
                actividad.fase = fase
                actividad.save()

                if requiere_insumo:
                    insumo_formset.instance = actividad
                    insumo_formset.save()

                if tipo.requiere_vist:
                    CamposVistoria.objects.create(actividad=actividad)

                if tipo.requiere_cosecha:
                    CamposCosecha.objects.create(actividad=actividad)

                if cierra_fase:
                    if not fase or fase.estado != "abierto":
                        messages.error(request, "No hay una fase abierta para cerrar.")
                        return render(request, "vista_agregar_actividad.html", context)

                    fase.fecha_fin = fecha
                    fase.estado = "cerrado"
                    fase.save()

                messages.success(request, "Actividad registrada correctamente.")
                return redirect("vista_detalle_ciclo", id_ciclo=ciclo.id)

            except Exception as e:
                messages.error(request, f"Error al registrar la actividad: {e}")

        else:
            messages.error(request, "Hay errores en el formulario.")

    else:
        actividad_form = ActividadProductivaForm()
        insumo_formset = ActividadInsumoFormSet(prefix="insumos")

    context = {
        "ciclo": ciclo,
        "actividad_form": actividad_form,
        "insumo_formset": insumo_formset,
    }

    return render(request, "vista_agregar_actividad.html", context)

@login_required
def ajax_productos_por_actividad(request):
    tipo_id = request.GET.get("tipo_id")
    subtipo_id = request.GET.get("subtipo_id")

    if not tipo_id:
        return JsonResponse({"ok": False, "productos": []})

    empresa = request.user.profile.empresa

    try:
        tipo = TipoActividad.objects.get(id=tipo_id, activo=True)
    except TipoActividad.DoesNotExist:
        return JsonResponse({"ok": False, "productos": []})

    configuraciones = TipoActividadCategoriaProducto.objects.filter(
        tipo_actividad=tipo,
        activo=True
    )

    if subtipo_id:
        configuraciones_subtipo = configuraciones.filter(subtipo_actividad_id=subtipo_id)

        if configuraciones_subtipo.exists():
            configuraciones = configuraciones_subtipo
        else:
            configuraciones = configuraciones.filter(subtipo_actividad__isnull=True)
    else:
        configuraciones = configuraciones.filter(subtipo_actividad__isnull=True)

    categoria_ids = configuraciones.values_list("categoria_producto_id", flat=True)

    productos = Producto.objects.filter(
        empresa=empresa,
        activo=True,
        categoria_id__in=categoria_ids
    ).order_by("nombre")

    data = [
        {
            "id": producto.id,
            "nombre": producto.nombre
        }
        for producto in productos
    ]

    return JsonResponse({
        "ok": True,
        "productos": data
    })