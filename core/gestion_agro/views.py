from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from gestion_agro.forms import CampoForm, CampanaForm, CicloForm
from gestion_agro.models import Campo, Campana, CicloAgricola


@login_required
def vista_campos(request):
    empresa = request.user.profile.empresa
    campos = Campo.objects.filter(empresa=empresa)

    if request.method == "POST":
        form = CampoForm(request.POST, request.FILES)
        if form.is_valid():
            campo = form.save(commit=False)
            campo.empresa = empresa
            campo.save()
            messages.success(request, _("Campo creado correctamente"))
            return redirect("vista_campos")
    else:
        form = CampoForm()

    return render(
        request,
        "vista_campo.html",
        {
            "form": form,
            "campos": campos,
            "empresa": empresa,
        },
    )

@login_required
def editar_campos(request, id_campo):
    campos = Campo.objects.filter(empresa = request.user.profile.empresa)
    try:
        campo = Campo.objects.get(id = id_campo)
    except:
        return redirect('vista_campos')
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
                return redirect('vista_campos')
            else:
                messages.error(request, form.errors.as_data() )
        else:
            form = CampoForm(instance = campo)
        return render(request, 'vista_campo.html', {'form': form, 'campos': campos, 'empresa': empresa, 'modificacion': 'S'})
    else:
        return redirect('vista_campos')

@login_required
def vista_campanas(request):
    empresa = request.user.profile.empresa

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
                return redirect("vista_campana")

            campana.save()
            messages.success(request, _("Campaña creada correctamente"))
            return redirect("vista_campana")
    else:
        form = CampanaForm()

    campanas = Campana.objects.filter(empresa=empresa)

    return render(
        request,
        "vista_campana.html",
        {
            "form": form,
            "campanas": campanas,
            "empresa": empresa,
        },
    )

@login_required
def editar_campana(request, id_campana):
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
def vista_lista_ciclo(request):

    empresa = request.user.profile.empresa

    ciclos = (
        CicloAgricola.objects
        .filter(campo__empresa=empresa)
        .select_related("campo", "campana", "cultivo")
        .order_by("-fecha_inicio")
    )

    for c in ciclos:
        print(
            f"ID:{c.id} | "
            f"Campo:{c.campo.nombre} | "
            f"Lote:{c.nombre_lote} | "
            f"Cultivo:{c.cultivo} | "
            f"Inicio:{c.fecha_inicio} | "
            f"Ha:{c.superficie_ha}"
        )

    return render(request, "vista_lista_ciclos.html", {"ciclos": ciclos })

@login_required
def vista_crear_ciclo(request):

    if request.method == "POST":
        form = CicloForm(request.POST)

        if form.is_valid():
            ciclo = form.save(commit=False)
            campo = ciclo.campo
            campana = ciclo.campana
            ultimo_num = ( CicloAgricola.objects.filter(campo=campo, campana=campana).count())
            ciclo.nombre_lote = f"Lote-{ultimo_num + 1}"
            ciclo.activa = True
            ciclo.save()

            messages.success(request,_("Implantación creada correctamente. Ahora podés registrar actividades."))

            return redirect("lista_ciclo")

    else:
        form = CicloForm()

    return render(request, "vista_crear_ciclo.html", {"form": form})