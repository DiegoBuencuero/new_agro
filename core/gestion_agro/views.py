from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from .funciones_aux import (  obtener_fase_abierta, validar_reglas_basicas_actividad,   crear_fase_si_corresponde,
                            actividad_debe_cerrar_fase,
                            cerrar_fase,
                            )
from gestion_agro.forms import ( CampoForm, CampanaForm, CicloForm, CicloFiltroForm,
                                ActividadProductivaForm, ActividadInsumoForm, ActividadInsumoFormSet)
from gestion_agro.models import ( Campo, Campana, CicloAgricola, FaseAgricola, SubTipoActividad,
                                ActividadProductiva
                                )


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
    ciclo = get_object_or_404(CicloAgricola, id=id_ciclo, campo__empresa=empresa)

    if not ciclo.activa:
        messages.error(request, _("El ciclo está cerrado."))
        return redirect("vista_detalle_ciclo", id_ciclo=ciclo.id)

    try:
        fase = obtener_fase_abierta(ciclo)
    except ValidationError as e:
        messages.error(request, e.message)
        return redirect("vista_detalle_ciclo", id_ciclo=ciclo.id)

    if request.method == "POST":
        actividad_form = ActividadProductivaForm(request.POST)
        insumo_formset = ActividadInsumoFormSet(request.POST, prefix="insumos")

        if actividad_form.is_valid() and insumo_formset.is_valid():
            tipo_actividad = actividad_form.cleaned_data["tipo"]
            subtipo = actividad_form.cleaned_data["subtipo"]
            fecha = actividad_form.cleaned_data["fecha"]

            try:
                if fase:
                    validar_reglas_basicas_actividad(
                        ciclo=ciclo,
                        fase=fase,
                        tipo_actividad=tipo_actividad,
                        subtipo=subtipo,
                        fecha=fecha,
                    )
                else:
                    validar_reglas_basicas_actividad(
                        ciclo=ciclo,
                        fase=None,
                        tipo_actividad=tipo_actividad,
                        subtipo=subtipo,
                        fecha=fecha,
                    )
                    fase = crear_fase_si_corresponde(
                        ciclo=ciclo,
                        tipo_actividad=tipo_actividad,
                        subtipo=subtipo,
                        fecha=fecha,
                    )

                actividad = actividad_form.save(commit=False)
                actividad.fase = fase
                actividad.save()

                insumo_formset.instance = actividad
                insumo_formset.save()

                if actividad_debe_cerrar_fase(
                    fase=fase,
                    tipo_actividad=tipo_actividad,
                    subtipo=subtipo,
                ):
                    cerrar_fase(fase, fecha)

            except ValidationError as e:
                messages.error(request, e.message)
                context = {
                    "ciclo": ciclo,
                    "actividad_form": actividad_form,
                    "insumo_formset": insumo_formset,
                }
                return render(request, "vista_agregar_actividad.html", context)

            messages.success(request, _("Actividad registrada correctamente."))
            return redirect("vista_detalle_ciclo", id_ciclo=ciclo.id)

    else:
        actividad_form = ActividadProductivaForm()
        insumo_formset = ActividadInsumoFormSet(prefix="insumos")

    context = {
        "ciclo": ciclo,
        "actividad_form": actividad_form,
        "insumo_formset": insumo_formset,
    }

    return render(request, "vista_agregar_actividad.html", context)
