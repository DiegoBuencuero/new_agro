from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from gestion_agro.forms import CampoForm, CampanaForm, CicloForm, CicloFiltroForm
from gestion_agro.models import Campo, Campana, CicloAgricola


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

    ciclos = CicloAgricola.objects.filter( campo__empresa=empresa ).select_related("campo", "campana", "cultivo").order_by( "-fecha_inicio" )

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

    else:
        ciclos = ciclos.filter(activa=True)

    lista_data = []

    for ciclo in ciclos:
        item = {
            "id": ciclo.id,
            "campo": ciclo.campo.nombre if ciclo.campo else "",
            "campana": str(ciclo.campana) if ciclo.campana else "",
            "nombre_lote": ciclo.nombre_lote if ciclo.nombre_lote else "",
            "cultivo": str(ciclo.cultivo) if ciclo.cultivo else "",
            "superficie_ha": float(ciclo.superficie_ha) if ciclo.superficie_ha is not None else "",
            "fecha_inicio": ciclo.fecha_inicio.strftime("%d/%m/%Y") if ciclo.fecha_inicio else "",
            "estado": "Cerrado" if ciclo.fecha_fin else "Activo",
        }
        lista_data.append(item)

    data = {
        "response": 0,
        "data": lista_data
    }

    return JsonResponse(data)

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

from django.http import HttpResponse

@login_required
def vista_detalle_ciclo(request, id_ciclo):
    empresa = request.user.profile.empresa

    ciclo = CicloAgricola.objects.filter(campo__empresa=empresa, id=id_ciclo).first()

    context = {
        "ciclo": ciclo,
    }

    return render(request, "vista_detalle_ciclo.html", context)


# @login_required
# def vista_detalle_ciclo(request, id):
#     empresa = request.user.profile.empresa

#     ciclo = get_object_or_404(
#         CicloAgricola,
#         id=id,
#         campo__empresa=empresa
#     )

#     # ===============================
#     # FASES
#     # ===============================
#     fases = list(
#         FaseAgricola.objects
#         .filter(ciclo=ciclo)
#         .order_by("fecha_inicio")
#     )
#     fase_activa = next((f for f in fases if f.estado == "abierto"), None)

#     # ===============================
#     # ACTIVIDADES (una sola query)
#     # ===============================
#     actividades = list(
#         ActividadProductiva.objects
#         .filter(fase__ciclo=ciclo)
#         .order_by("-fecha")
#     )

#     # ===============================
#     # COSTOS POR ACTIVIDAD
#     # ===============================
#     costo_total_ciclo = Decimal("0")

#     for act in actividades:
#         total_act = (
#             ConsumoStock.objects
#             .filter(movimiento_salida__actividad=act)
#             .aggregate(total=Sum("costo_total"))
#             .get("total")
#             or Decimal("0")
#         )

#         act.costo_total_actividad = total_act
#         costo_total_ciclo += total_act


#     # ===============================
#     # COSTOS POR FASE
#     # ===============================
#     costos_por_fase = []

#     for fase in fases:
#         total_fase = sum(
#             act.costo_total_actividad
#             for act in actividades
#             if act.fase_id == fase.id
#         )

#         costos_por_fase.append({
#             "fase": fase,
#             "fase_id": fase.id,
#             "costo_total": total_fase
#         })

#     # ===============================
#     # MÉTRICAS BASE
#     # ===============================
#     superficie = ciclo.superficie_ha or Decimal("1")

#     costo_ha_ciclo = (
#         costo_total_ciclo / superficie
#         if superficie > 0
#         else Decimal("0")
#     )

#     # ===============================
#     # PRECIO (VIENE DEL DASHBOARD)
#     # ===============================
#     precio_saco = Decimal(
#         request.session.get("precio_saco", 0)
#     )

#     # ===============================
#     # MÉTRICAS EN SACOS
#     # ===============================
#     sacos_equilibrio_ha = (
#         costo_ha_ciclo / precio_saco
#         if precio_saco > 0
#         else Decimal("0")
#     )

#     # ===============================
#     # FECHA DE COSECHA (FIN REAL)
#     # ===============================

#     cosecha_principal = next(
#         (
#             a for a in actividades
#             if a.tipo.lower() == "cosecha"
#             and not a.es_desecado
#         ),
#         None
#     )

#     fecha_fin_real = cosecha_principal.fecha if cosecha_principal else None

#     return render(
#         request,
#         "vista_detalle_ciclo.html",
#         {
#             # entidades
#             "ciclo": ciclo,
#             "fases": fases,
#             "fase_activa": fase_activa,
#             "actividades": actividades,

#             # costos
#             "costo_total_ciclo": costo_total_ciclo,
#             "costo_ha_ciclo": costo_ha_ciclo,
#             "costos_por_fase": costos_por_fase,

#             # mercado
#             "precio_saco": precio_saco,

#             # métricas
#             "sacos_equilibrio_ha": sacos_equilibrio_ha,

#             # totales
#             "total_actividades": len(actividades),
#             "total_fases": len(fases),
#             "fecha_fin_real": fecha_fin_real,
#         }
#     )

def vista_editar_ciclo():
    pass


@login_required
def vista_agregar_actividad(request, id_ciclo):
    empresa = request.user.profile.empresa
    ciclo = CicloAgricola.objects.filter(
        id=id_ciclo,
        campo__empresa=empresa
    ).first()

    if not ciclo:
        messages.error(request, "El ciclo no existe o no pertenece a su empresa.")
        return redirect("vista_lista_ciclos")

    if not ciclo.activa:
        messages.error(request, "El ciclo está cerrado.")
        return redirect("vista_detalle_ciclo", id_ciclo=ciclo.id)

    context = {
        "ciclo": ciclo,
    }

    return render(request, "vista_agregar_actividad.html", context)