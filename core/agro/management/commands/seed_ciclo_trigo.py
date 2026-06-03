"""
Ciclo de Trigo 2025 - ALTA para iBICUI
Basado en la planilla: Produtividade 4.200 kg/ha, Plantio Direto na Palha
"""
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed ciclo trigo 2025 iBICUI con insumos, MO y cosecha exactos"

    def add_arguments(self, parser):
        parser.add_argument("--empresa", default="Agroinnova")
        parser.add_argument("--campo",   default="iBICUI")
        parser.add_argument("--sup",     type=float, default=210.0)

    def handle(self, *args, **options):
        from agro.models import Empresa, Unidad
        from gestion_agro.models import (
            Campo, Campana, Cultivo, CicloAgricola, FaseAgricola,
            ActividadProductiva, ActividadInsumo,
            CamposCosecha, MovimientoStock,
            TipoActividad, SubTipoActividad,
            Deposito, Producto, CategoriaProducto,
        )

        emp   = Empresa.objects.get(nombre=options["empresa"])
        campo = Campo.objects.get(nombre=options["campo"], empresa=emp)
        camp  = Campana.objects.filter(empresa=emp).first()
        trigo = Cultivo.objects.get(nombre="Trigo", empresa=emp)
        dep   = Deposito.objects.filter(empresa=emp).first()
        SUP   = Decimal(str(options["sup"]))

        kg   = Unidad.objects.get(abreviatura="kg")
        L    = Unidad.objects.get(abreviatura="L")
        g    = Unidad.objects.get(abreviatura="g")

        # ── Asegurar productos que no están en el seed base ───────────────────
        cat_agro = CategoriaProducto.objects.get(codigo="AGROQUIMICO")
        cat_fert = CategoriaProducto.objects.get(codigo="FERTILIZANTE")
        cat_sem  = CategoriaProducto.objects.get(codigo="SEMILLA")
        cat_ins  = CategoriaProducto.objects.get(codigo="INSUMO")

        def get_or_create_prod(codigo, nombre, cat, unidad):
            p, cr = Produto = Produto = None, None
            p, cr = Producto.objects.get_or_create(
                empresa=emp, codigo=codigo,
                defaults={"nombre": nombre, "categoria": cat, "unidad_base": unidad,
                          "activo": True, "maneja_stock": True}
            )
            if cr: self.stdout.write(f"  Producto creado: {nombre}")
            return p

        TRI   = get_or_create_prod("SEM-TRI-1",  "Semente Trigo Ametista",       cat_sem,  kg)
        NPK_8 = get_or_create_prod("FRT-NPK820", "Fertilizante NPK 8-20-20",     cat_fert, kg)
        GRAM  = get_or_create_prod("HRB-GRAM",   "Herbicida Dessecante WG",       cat_agro, kg)
        SEL   = get_or_create_prod("HRB-SEL",    "Herbicida Select One Pack",     cat_agro, L)
        ASST  = get_or_create_prod("ADJ-ASST",   "Assist Óleo Vegetal",           cat_agro, L)
        ALLY  = get_or_create_prod("HRB-ALLY",   "Herbicida Pós Ally",            cat_agro, g)
        MODD  = get_or_create_prod("REG-MODD",   "Regulador Moddus",              cat_agro, L)
        UREIA = get_or_create_prod("FRT-003",    "Ureia 45% N",                   cat_fert, kg)
        TRAT  = get_or_create_prod("SEM-TRAT",   "Tratamento Semente Industrial", cat_ins,  kg)
        NATIVO = get_or_create_prod("FNG-NATV",  "Fungicida Nativo",              cat_agro, L)
        FOXXP  = get_or_create_prod("FNG-FOXX",  "Fungicida Fox Xpro",            cat_agro, L)
        ABACUS = get_or_create_prod("FNG-ABAC",  "Fungicida Abacus",              cat_agro, L)
        ENGEO  = get_or_create_prod("INS-ENGEO", "Inseticida Engeo Pleno S",      cat_agro, L)
        AMPLI  = get_or_create_prod("INS-AMPL",  "Inseticida Ampligo",            cat_agro, L)
        CERT   = get_or_create_prod("INS-CERT",  "Inseticida Certero",            cat_agro, L)

        # ── Tipos de actividad ────────────────────────────────────────────────
        def tipo(n):    return TipoActividad.objects.get(nombre=n)
        def sub(t, c):  return SubTipoActividad.objects.get(tipo_actividad=t, codigo=c)

        t_plant = tipo("Plantio + Adubação")
        t_adub  = tipo("Adubação cobertura")
        t_aplic = tipo("Aplicação")
        t_colh  = tipo("Colheita")
        t_trat  = tipo("Tratamento sementes")

        s_des  = sub(t_aplic, "DES")
        s_her  = sub(t_aplic, "HER")
        s_fun  = sub(t_aplic, "FUN")
        s_ifu  = sub(t_aplic, "IFU")
        s_hin  = sub(t_aplic, "HIN")
        s_fol  = sub(t_aplic, "FOL")

        # ── Ciclo ─────────────────────────────────────────────────────────────
        ciclo, _ = CicloAgricola.objects.get_or_create(
            campo=campo, campana=camp, cultivo=trigo,
            defaults={
                "nombre_lote":    f"{campo.nombre} - Trigo 25",
                "superficie_ha":  SUP,
                "fecha_inicio":   date(2025, 5, 15),
                "fecha_fin":      date(2025, 12, 10),
                "activa":         False,
                "producto_final": trigo.producto_default,
            }
        )
        self.stdout.write(f"Ciclo: {ciclo}")

        fase, _ = FaseAgricola.objects.get_or_create(
            ciclo=ciclo, tipo="PRI",
            defaults={"fecha_inicio": date(2025, 5, 15),
                      "fecha_fin":    date(2025, 12, 10),
                      "estado": "cerrado"}
        )

        # ── Helpers ───────────────────────────────────────────────────────────
        def act(fecha, tipo_act, sub_act, mo_dia, maq_h, v_maq=100):
            V_MO = 140
            a, _ = ActividadProductiva.objects.get_or_create(
                fase=fase, fecha=fecha, tipo=tipo_act,
                defaults={
                    "subtipo":         sub_act,
                    "cantidad_hombre": Decimal(str(round(mo_dia * float(SUP), 2))),
                    "valor_hombre":    Decimal(str(V_MO)),
                    "cantidad_h_maq":  Decimal(str(round(maq_h * float(SUP), 2))),
                    "valor_h_maq":     Decimal(str(v_maq)),
                    "total_mo":        Decimal(str(round(mo_dia * float(SUP) * V_MO, 2))),
                    "total_maq":       Decimal(str(round(maq_h * float(SUP) * v_maq, 2))),
                    "total":           Decimal(str(round((mo_dia*V_MO + maq_h*v_maq)*float(SUP), 2))),
                }
            )
            return a

        def ins(actividad, prod, dosis, um, precio_unit):
            cant = Decimal(str(round(float(dosis) * float(SUP), 2)))
            ActividadInsumo.objects.get_or_create(
                actividad=actividad, producto=prod,
                defaults={
                    "dosis":         Decimal(str(dosis)),
                    "um":            um,
                    "cantidad_real": cant,
                    "costo_total":   Decimal(str(round(float(precio_unit) * float(dosis) * float(SUP), 2))),
                    "costo_ha":      Decimal(str(round(float(precio_unit) * float(dosis), 2))),
                }
            )

        # ══════════════════════════════════════════════════════════════════════
        # ACTIVIDADES (exactas del cuadro de costos)
        # ══════════════════════════════════════════════════════════════════════

        # 1. Tratamento Sementes (May)
        # MO: 0.05 dia-h × R$140 = R$7/ha
        a_trat = act(date(2025, 5, 20), t_trat, None, 0.05, 0.0)
        ins(a_trat, TRAT, 4,    kg, 26.00)   # 4 doses @ R$26/dose

        # 2. Aplic. Dessecante (May)
        # MO: 0.1 dia-h × R$140 = R$14/ha
        # Maq: 1.2h × R$100 = R$120/ha
        a_des = act(date(2025, 5, 25), t_aplic, s_des, 0.10, 1.2, 100)
        ins(a_des, GRAM, 1.50, kg, 51.80)   # Herbicida WG 1.5kg/ha @ R$51.80
        ins(a_des, SEL,  1.20, L,  52.00)   # Select One Pack 1.2L/ha @ R$52
        ins(a_des, ASST, 0.50, L,  28.65)   # Assist 0.5L/ha @ R$28.65

        # 3. Plantio + Adubação Base (Jun)
        # MO: 0.2 dia-h × R$140 = R$28/ha
        # Maq: 1.0h × R$140 = R$140/ha (plantadeira)
        a_plan = act(date(2025, 6, 10), t_plant, None, 0.20, 1.0, 140)
        ins(a_plan, TRI,   200, kg, 3.40)   # Semente 200kg/ha @ R$3.40
        ins(a_plan, NPK_8, 350, kg, 3.32)   # NPK 8-20-20 350kg/ha @ R$3.32

        # 4. Aplic. Herbicida Pós (Jul)
        # MO: 0.4 dia-h × R$140 = R$56/ha
        # Maq: 1.2h × R$100 = R$120/ha
        a_herb = act(date(2025, 7, 5), t_aplic, s_her, 0.40, 1.2, 100)
        ins(a_herb, ALLY, 8.0,  g, 1.50)   # Ally 8gr/ha @ R$1.50/gr
        ins(a_herb, MODD, 0.40, L, 168.51) # Moddus 0.4L/ha @ R$168.51

        # 5. Adubação Cobertura (Jul)
        # MO: incluida en Aplic. Herb. (mismo dia según cuadro)
        # Maq: 0.5h × R$100 = R$50/ha
        a_cob = act(date(2025, 7, 20), t_adub, None, 0.00, 0.5, 100)
        ins(a_cob, UREIA, 200, kg, 2.74)   # Ureia Plus 200kg/ha @ R$2.74

        # 6. Aplic. Inset. + Fung. 1ª (Aug)
        # Maq: 1.2h × R$100 = R$120/ha
        a_if1 = act(date(2025, 8, 10), t_aplic, s_ifu, 0.00, 1.2, 100)
        ins(a_if1, NATIVO, 0.75, L, 115.00)  # Nativo 0.75L/ha @ R$115
        ins(a_if1, ENGEO,  0.25, L, 254.00)  # Engeo Pleno S 0.25L/ha

        # 7. Aplic. Inset. + Fung. 2ª (Sep)
        # Maq: 1.2h × R$100 = R$120/ha
        a_if2 = act(date(2025, 9, 5), t_aplic, s_ifu, 0.00, 1.2, 100)
        ins(a_if2, FOXXP,  0.50, L, 340.00)  # Fox Xpro 0.5L/ha
        ins(a_if2, ABACUS, 0.40, L, 255.00)  # Abacus 0.4L/ha
        ins(a_if2, AMPLI,  0.06, L, 422.00)  # Ampligo 0.06L/ha
        ins(a_if2, CERT,   0.10, L, 252.93)  # Certero 0.1L/ha

        # 8. Colheita (Nov/Dec)
        # MO: 0.2 dia-h × R$140 = R$28/ha
        # Maq: 1.0h × R$280 = R$280/ha (colhedora)
        a_colh = act(date(2025, 11, 20), t_colh, None, 0.20, 1.0, 280)

        # Rendimento: 4.200 kg/ha (exacto del cuadro)
        rend_ha = Decimal("4200.00")
        cosecha, _ = CamposCosecha.objects.get_or_create(
            actividad=a_colh,
            defaults={
                "rendimiento": rend_ha,
                "comentarios_cosecha": f"Trigo 2025 {campo.nombre} — ALTA 4.200 kg/ha — Plantio Direto",
            }
        )

        if trigo.producto_default and dep:
            MovimientoStock.objects.get_or_create(
                cosecha=cosecha,
                defaults={
                    "producto":         trigo.producto_default,
                    "tipo":             "ENTRADA",
                    "cantidad":         rend_ha * SUP,
                    "um":               kg,
                    "deposito_destino": dep,
                    "precio_unitario":  Decimal("0.85"),  # R$0.85/kg trigo
                    "actividad":        a_colh,
                }
            )

        # ── Resumen ───────────────────────────────────────────────────────────
        acts = ActividadProductiva.objects.filter(fase=fase).count()
        total_insumos_ha = 3200.19
        total_mo_ha      = 133.00
        total_maq_ha     = 950.00
        total_ha         = total_insumos_ha + total_mo_ha + total_maq_ha

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Ciclo Trigo cargado: {ciclo}\n"
            f"  Superficie:     {SUP} ha\n"
            f"  Actividades:    {acts}\n"
            f"  Rendimento:     {rend_ha} kg/ha\n"
            f"  Producción:     {float(rend_ha)*float(SUP)/1000:.0f} tn ({float(rend_ha)*float(SUP)/60:.0f} sc)\n"
            f"  Costo insumos:  R$ {total_insumos_ha:,.2f}/ha\n"
            f"  Costo MO:       R$ {total_mo_ha:,.2f}/ha\n"
            f"  Costo mecânicos:R$ {total_maq_ha:,.2f}/ha\n"
            f"  COSTO TOTAL:    R$ {total_ha:,.2f}/ha  |  R$ {total_ha*float(SUP):,.0f} total\n"
        ))
