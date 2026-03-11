from django.test import TestCase

@login_required
def vista_crear_ciclo(request):

    empresa = request.user.profile.empresa

    if request.method == "POST":
        form = CicloForm(empresa, request.POST)

        if form.is_valid():

            ciclo = form.save(commit=False)

            campo = ciclo.campo
            campana = ciclo.campana
            ultimo_num = (
                CicloAgricola.objects
                .filter(
                    campo=campo,
                    campana=campana
                )
                .count()
            )

            ciclo.nombre_lote = f"Lote-{ultimo_num + 1}"
            ciclo.activa = True

            ciclo.save()
            print("Implantación guardada OK")

            messages.success(
                request,
                "Implantación creada correctamente. Ahora podés registrar actividades."
            )

        return redirect("lista_ciclo")

    else:
        form = CicloForm(empresa)

    return render(
        request,
        "vista_ciclo.html",
        {
            "form": form
        }
    )

@login_required
def vista_cerrar_ciclo(request, id_ciclo):

    ciclo= get_object_or_404(
        CicloAgricola,
        id=id_ciclo,
        campo__empresa=request.user.profile.empresa
    )

    if ciclo.fecha_fin:
        messages.warning(request, "La implantación ya está cerrada.")
        return redirect("vista_lista_ciclos")

    if request.method == "POST":
        form = CerrarCicloForm(request.POST, instance=ciclo)

        if form.is_valid():
            imp = form.save(commit=False)
            imp.activa = False
            imp.save()

            messages.success(
                request,
                f"Implantación {imp.nombre_lote} cerrada correctamente."
            )

            return redirect("lista_ciclo")

    else:
        form = CerrarCicloForm(instance=ciclo)

    return render(
        request,
        "vista_cerrar_implantacion.html",
        {
            "ciclo": ciclo,
            "form": form,
        }
    )


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
    return render(
        request,
        "vista_lista_ciclos.html",
        {
            "ciclos": ciclos,
        }
    )

