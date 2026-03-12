from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from gestion_agro.forms import CampoForm, CampanaForm, CicloForm
from gestion_agro.models import Campo, Campana, CicloAgricola


# @login_required
# def vista_crear_campo(request):
#     empresa = request.user.profile.empresa
#     campos = Campo.objects.filter(empresa=empresa)

#     if request.method == "POST":
#         form = CampoForm(request.POST, request.FILES)
#         if form.is_valid():
#             campo = form.save(commit=False)
#             campo.empresa = empresa
#             campo.save()
#             messages.success(request, _("Campo creado correctamente"))
#             return redirect("vista_crear_campo")
#     else:
#         form = CampoForm()

#     return render(
#         request,
#         "vista_crear_campo.html",
#         {
#             "form": form,
#             "campos": campos,
#             "empresa": empresa,
#         },
#     )
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
    campana_id = request.GET.get("campana")

    campanas = (Campana.objects.filter(empresa=empresa).order_by("-fecha_desde"))

    ciclos = (CicloAgricola.objects.filter(campo__empresa=empresa)
        .select_related("campo", "campana", "cultivo")
        .order_by("-fecha_inicio")
    )
    campana_seleccionada = None

    if campana_id:
        ciclos = ciclos.filter(campana_id=campana_id)
        campana_seleccionada = campana_id
    else:
        campana_activa = (Campana.objects.filter(empresa=empresa, activa=True).first())

        if campana_activa:
            ciclos = ciclos.filter(campana=campana_activa)
            campana_seleccionada = str(campana_activa.id)

    context = {
        "ciclos": ciclos,
        "campanas": campanas,
        "campana_seleccionada": campana_seleccionada,
    }

    return render(request, "vista_lista_ciclos.html", context)


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

def vista_detalle_ciclo():
    pass

def vista_editar_ciclo():
    pass