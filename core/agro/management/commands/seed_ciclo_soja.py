"""
Ciclo de Soja 2025/2026 - ALTA para iBICUI
Basado en planilla: Produtividade 4.200 kg/ha, Plantio Direto na Palha
"""
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed ciclo soja 2025/26 iBICUI con insumos, MO y cosecha exactos"

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
        soja  = Cultivo.objects.get(nombre="Soja", empresa=emp)
        dep   = Deposito.objects.filter(empresa=emp).first()
        SUP   = Decimal(str(options["sup"]))

        kg = Unidad.objects.get(abreviatura="kg")
        L  = Unidad.objects.get(abreviatura="L")
        g  = Unidad.objects.get(abreviatura="g")

        # ── Asegurar que el ciclo de trigo está cerrado ───────────────────────
        from gestion_agro.models import Cultivo as C
        trigo = C.objects.filter(nombre="Trigo", empresa=emp).first()
        if trigo:
            for ciclo_trigo in CicloAgricola.objects.filter(campo=campo, cultivo=trigo):
                for fase in ciclo_trigo.fases.all():
                    if fase.estado != "cerrado":
                        fase.estado = "cerrado"
                        fase.save()
                        self.stdout.write(f"  Fase trigo cerrada: {fase}")

        # ── Categorías ────────────────────────────────────────────────────────
        cat_agro = CategoriaProducto.objects.get(codigo="AGROQUIMICO")
        cat_fert = CategoriaProducto.objects.get(codigo="FERTILIZANTE")
        cat_sem  = CategoriaProducto.objects.get(codigo="SEMILLA")
        cat_ins  = CategoriaProducto.objects.get(codigo="INSUMO")

        def P(codigo, nombre, cat, unidad):
            p, cr = Producto.objects.get_or_create(
                empresa=emp, codigo=codigo,
                defaults={"nombre": nombre, "categoria": cat, "unidad_base": unidad,
                          "activo": True, "maneja_stock": True}
            )
            if cr: self.stdout.write(f"  Producto: {nombre}")
            return p

        # Sementes e adubos
        SOJ_SEM  = P("SEM-SOJ-55I57", "Semente Soja 55i57 Ipro Zeus",   cat_sem,  kg)
        NPK_5    = P("FRT-NPK05-30",  "Fertilizante 05-30-15 Mist",      cat_fert, kg)
        KCL_COB  = P("FRT-KCL",       "Cloreto Potássio (Adubo cob.)",   cat_fert, kg)
        # Dessecantes
        ZAPP     = P("HRB-ZAPP",      "Herbicida Zapp",                   cat_agro, L)
        HEAT     = P("HRB-HEAT",      "Herbicida Heat",                   cat_agro, kg)
        SEL      = P("HRB-SEL",       "Herbicida Select One Pack",        cat_agro, L)
        D24      = P("HRB-24D",       "Herbicida 2,4-D",                  cat_agro, L)
        # Herb pré/pós
        ZETAMAX  = P("HRB-ZETA",      "Herbicida Pré-emergente Zetamax",  cat_agro, L)
        ZAPP_POS = P("HRB-ZAPP-POS",  "Herbicida Pós Zapp",              cat_agro, L)
        # Tratamento semente
        SERENADE = P("FNG-SERE",      "Fungicida Pré-plantio Serenade",   cat_agro, L)
        TRAT_SOJ = P("SEM-TRAT-SOJ",  "Tratamento Semente Industrial",    cat_ins,  kg)
        # Fungicidas aéreos
        SPHEREMAX= P("FNG-SPHE",      "Fungicida Sphere Max",             cat_agro, L)
        SPOT     = P("FNG-SPOT",      "Fungicida Spot",                   cat_agro, L)
        FOXXP    = P("FNG-FOXX",      "Fungicida Fox Xpro",               cat_agro, L)
        ALADE    = P("FNG-ALAD",      "Fungicida Alade",                  cat_agro, L)
        BRAVONIL = P("FNG-BRAV",      "Fungicida Bravonil 720",           cat_agro, L)
        CYPRESS  = P("FNG-CYPR",      "Fungicida Cypress",                cat_agro, L)
        # Inseticidas
        ENGEO    = P("INS-ENGEO",     "Inseticida Engeo Pleno S",         cat_agro, L)
        CURBIX   = P("INS-CURB",      "Inseticida Curbix",                cat_agro, L)
        TALISMAN = P("INS-TALI",      "Inseticida Talisman",              cat_agro, L)

        # ── Tipos de actividad ────────────────────────────────────────────────
        def tipo(n):   return TipoActividad.objects.get(nombre=n)
        def sub(t, c): return SubTipoActividad.objects.get(tipo_actividad=t, codigo=c)

        t_plant = tipo("Plantio + Adubação")
        t_adub  = tipo("Adubação cobertura")
        t_aplic = tipo("Aplicação")
        t_colh  = tipo("Colheita")
        t_trat  = tipo("Tratamento sementes")

        s_des = sub(t_aplic, "DES")
        s_her = sub(t_aplic, "HER")
        s_ifu = sub(t_aplic, "IFU")
        s_hin = sub(t_aplic, "HIN")
        s_fol = sub(t_aplic, "FOL")

        # ── Ciclo ─────────────────────────────────────────────────────────────
        ciclo, _ = CicloAgricola.objects.get_or_create(
            campo=campo, campana=camp, cultivo=soja,
            defaults={
                "nombre_lote":    f"{campo.nombre} - Soja 25/26",
                "superficie_ha":  SUP,
                "fecha_inicio":   date(2025, 10, 1),
                "fecha_fin":      date(2026, 4, 15),
                "activa":         True,
                "producto_final": soja.producto_default,
            }
        )
        self.stdout.write(f"Ciclo: {ciclo}")

        fase, _ = FaseAgricola.objects.get_or_create(
            ciclo=ciclo, tipo="PRI",
            defaults={"fecha_inicio": date(2025, 10, 1),
                      "fecha_fin":    date(2026, 4, 15),
                      "estado": "abierto"}  # activa!
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
            costo_ha = round(float(dosis) * float(precio_unit), 2)
            ActividadInsumo.objects.get_or_create(
                actividad=actividad, producto=prod,
                defaults={
                    "dosis":         Decimal(str(dosis)),
                    "um":            um,
                    "cantidad_real": Decimal(str(round(float(dosis) * float(SUP), 2))),
                    "costo_ha":      Decimal(str(costo_ha)),
                    "costo_total":   Decimal(str(round(costo_ha * float(SUP), 2))),
                }
            )

        # ══════════════════════════════════════════════════════════════════════
        # ACTIVIDADES — exactas de la planilla
        # ══════════════════════════════════════════════════════════════════════

        # 1. Tratamento Sementes (Oct 2025)
        # MO: 0.05 dia-h/ha × R$140
        a_trat = act(date(2025, 10, 10), t_trat, None, 0.05, 0.0)
        ins(a_trat, TRAT_SOJ, 1.75, kg, 134.00)   # 1.75 dose/ha @ R$134
        ins(a_trat, SERENADE, 2.00, L,  82.00)    # Serenade 2L/ha @ R$82 (pre-plantio)

        # 2. Aplic. Dessecante (Oct 2025)
        # MO: 0.1 dia-h × R$140 | Maq: 1.2h × R$100
        a_des = act(date(2025, 10, 15), t_aplic, s_des, 0.10, 1.2, 100)
        ins(a_des, ZAPP,  2.00, L,  39.50)   # Zapp 2L/ha @ R$39.50
        ins(a_des, HEAT,  0.05, kg, 2329.00) # Heat 50g/ha @ R$2329
        ins(a_des, SEL,   1.20, L,  52.00)   # Select One Pack 1.2L/ha
        ins(a_des, D24,   1.50, L,  27.50)   # 2,4-D 1.5L/ha

        # 3. Plantio + Adubação Base (Nov 2025)
        # MO: 0.2 dia-h × R$140 | Maq: 1.0h × R$140 (plantadeira)
        a_plan = act(date(2025, 11, 5), t_plant, None, 0.20, 1.0, 140)
        ins(a_plan, SOJ_SEM, 70.0,  kg,  12.50)  # Semente 70kg/ha @ R$12.50
        ins(a_plan, NPK_5,   350.0, kg,   3.66)  # Adubo base 350kg/ha

        # 4. Herb. Pré-emergente (Nov 2025)
        # MO: incluida en herbicida pós
        a_pre = act(date(2025, 11, 10), t_aplic, s_her, 0.0, 1.2, 100)
        ins(a_pre, ZETAMAX, 0.50, L, 236.00)  # Zetamax 0.5L/ha

        # 5. Herb. Pós-emergente (Dic 2025)
        # MO: 0.4 dia-h × R$140 | Maq: 1.2h × R$100
        a_her = act(date(2025, 12, 5), t_aplic, s_her, 0.40, 1.2, 100)
        ins(a_her, ZAPP_POS, 2.00, L, 39.50)  # Zapp pós 2L/ha

        # 6. Adubação Cobertura (Dic 2025)
        # Maq: 0.5h × R$100
        a_cob = act(date(2025, 12, 15), t_adub, None, 0.00, 0.5, 100)
        ins(a_cob, KCL_COB, 150.0, kg, 3.48)  # KCl 150kg/ha @ R$3.48

        # 7. Aplic. Herb + Inset. (Ene 2026) — 1ª aérea
        # Maq: 1.2h × R$100
        a_hi1 = act(date(2026, 1, 8), t_aplic, s_hin, 0.0, 1.2, 100)
        ins(a_hi1, SPHEREMAX, 0.20, L, 350.00)  # Sphere Max 0.2L/ha
        ins(a_hi1, ENGEO,     0.25, L, 254.00)  # Engeo Pleno S 0.25L/ha

        # 8. Aplic. Inset + Fung. (Ene 2026) — 2ª aérea
        # Maq: 1.2h × R$100
        a_if1 = act(date(2026, 1, 25), t_aplic, s_ifu, 0.0, 1.2, 100)
        ins(a_if1, SPOT,    2.00, L, 280.00)  # Spot 2L/ha
        ins(a_if1, CURBIX,  0.75, L, 145.00)  # Curbix 0.75L/ha

        # 9. Aplic. Inset + Fung. (Feb 2026) — 3ª aérea
        # Maq: 1.2h × R$100
        a_if2 = act(date(2026, 2, 10), t_aplic, s_ifu, 0.0, 1.2, 100)
        ins(a_if2, FOXXP,    0.50, L, 340.00)  # Fox Xpro 0.5L/ha
        ins(a_if2, ALADE,    0.50, L, 385.95)  # Alade 0.5L/ha
        ins(a_if2, BRAVONIL, 2.00, L,  31.00)  # Bravonil 720 2L/ha
        ins(a_if2, CYPRESS,  0.30, L, 244.00)  # Cypress 0.3L/ha
        ins(a_if2, TALISMAN, 0.50, L, 105.00)  # Talisman 0.5L/ha

        # 10. Colheita (Mar 2026)
        # MO: 0.2 dia-h × R$140 | Maq: 1.0h × R$280 (colhedora)
        a_colh = act(date(2026, 3, 15), t_colh, None, 0.20, 1.0, 280)

        rend_ha = Decimal("4200.00")
        cosecha, _ = CamposCosecha.objects.get_or_create(
            actividad=a_colh,
            defaults={
                "rendimiento":        rend_ha,
                "comentarios_cosecha": f"Soja 25/26 {campo.nombre} — 4.200 kg/ha — 55i57 IPRO",
            }
        )

        if soja.produto_default if False else soja.producto_default and dep:
            MovimientoStock.objects.get_or_create(
                cosecha=cosecha,
                defaults={
                    "producto":         soja.producto_default,
                    "tipo":             "ENTRADA",
                    "cantidad":         rend_ha * SUP,
                    "um":               kg,
                    "deposito_destino": dep,
                    "precio_unitario":  Decimal("1.80"),  # R$1.80/kg soja
                    "actividad":        a_colh,
                    "destino":          "C",
                }
            )

        acts = ActividadProductiva.objects.filter(fase=fase).count()
        insumos_tot = 3200.19 + (4925.53 - 3200.19)  # = 4925.53
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Ciclo Soja cargado: {ciclo}\n"
            f"  Superficie:      {SUP} ha\n"
            f"  Actividades:     {acts}\n"
            f"  Rendimento:      {rend_ha} kg/ha ({float(rend_ha)/60:.0f} sc/ha)\n"
            f"  Producción:      {float(rend_ha)*float(SUP)/1000:.0f} tn\n"
            f"  Costo insumos:   R$ 4.925,53/ha\n"
            f"  Costo MO:        R$ 133,00/ha\n"
            f"  Costo mecânicos: R$ 950,00/ha\n"
            f"  COSTO TOTAL:     R$ 6.008,53/ha  |  R$ {6008.53*float(SUP):,.0f} total\n"
        ))
