---
name: ampliacion-new-agro
description: "Features de ampliación pendientes para new_agro, inspiradas en BrazSoft y otras referencias del usuario"
metadata: 
  node_type: memory
  type: project
  originSessionId: a5bf8fd7-c79f-4495-913c-bd3d5079d004
---

# Ampliaciones pendientes — new_agro

## Referencias vistas
- **BrazSoft** (swrural.com.br): sistema agro brasileño con mapa de costos, NFe, integración SEFAZ

## Features identificadas (el usuario seguirá agregando)

### 1. Centros de costo (PRIORIDAD ALTA)
Imputar facturas de compra a un campo/ciclo específico para análisis de costos por lote.
- FK de FacturaCompra o ítems → CicloAgricola
- Ver costo real por ciclo incluyendo facturas de insumos

### 2. Archivo de documentos (PRIORIDAD MEDIA)
Subir XML/PDF de NF-e vinculados a FacturaCompra.
- Campo archivo en FacturaCompra
- Visor o descarga desde la tabla de facturas

### 3. Integración SEFAZ (PRIORIDAD BAJA — requiere certificado digital e-CNPJ)
Traer automáticamente todas las NFe/CTe emitidas al CNPJ del cliente desde la API de SEFAZ.
- Requiere certificado digital por empresa
- Manifestación de ciência/confirmação
- Import automático de notas al sistema

### 4. Módulo Financiero completo (visto en BrazSoft → Controles Diarios → Financeiro)
- **Centros de Costos** — imputar gastos a campo/ciclo
- **Grupo Despesas e Receitas** — categorías de ingresos/egresos
- **Cotações** — tipos de cambio
- **Contas Bancárias** — cuentas bancarias de la empresa
- **Movimentações** — movimientos bancarios
- **Contas a Pagar/Receber** — similar a cuenta corriente actual pero más completo (vincula con banco, tipo de documento, forma de pago)
- **Créditos e Débitos**
- **Empréstimos** — préstamos
- **Conciliações** — conciliación bancaria

Cada cuenta/pago tiene: Pagar a (proveedor), Dados Bancários, Despesa/Receita (variable/fija), Tipo Despesa/Receita, Forma de Pagamento, Tipo de Documento (boleto, etc.), Num. Doc., Moeda.

### 5. Movimentações (Movimientos bancarios)
- Receita / Despesa / Transferência
- **Importar OFX** — importar extracto bancario desde archivo OFX (formato estándar de bancos)
- **Importar Documento Fiscal XML** (NF-e, NFS-e, CT-e) — leer XML y crear movimiento automáticamente
- Columnas: Tipo pago, N° Documento, Parcela, Fecha, Cuenta Bancaria, Pago a/Recibido de, Impuesto Renta, Movimiento, Valor

### 6. Estoque (Inventario/Compras) — visto en BrazSoft
- Materiales, Pedido de Compra, Autoriza Pedido, Cotações de Compras, Orden de Compra, Entradas, Consumos, Inventarios, Transferencias de Materiales, Compra y Venta de Materiales
- Flujo completo de compras con aprobación

### 10. Pesagens Avulsas — registro de pesaje de granos en entrega
Formulario para registrar entregas de granos con: Producto, Produtor, Destino Armazém, Contrato de Compra, Contrato a entregar, Variedade, Caminhão, Empresa Terceirizada, CPF/CNPJ, Valor Frete, N. Fiscal, Ticket, Data, Hora Pesagem, Lote + sección Pesagem.
→ Flujo logístico de comercialización de granos (camión → balanza → armazém).

### 16. Agricultura de Precisión — Capas de Análisis (PRIORIDAD ALTA - reunión miércoles)
Arquitectura: el usuario carga diferentes "capas" de análisis (suelo, nutrientes, NDVI, rendimiento, lluvia, etc.) como variables independientes. Al hacer click en el mapa, el sistema muestra TODAS las variables disponibles para ese punto en un panel comparativo unificado.

Modelos necesarios:
- **TipoCapa**: tipo de variable (N, P, K, pH, NDVI, rendimiento, lluvia, compactación, etc.)
- **CapaAnalisis**: una capa cargada para un campo/ciclo/fecha, con su tipo y datos geoespaciales
- **PuntoAnalisis**: valor de una variable en un punto geográfico (lat/lon + valor + capa)

Al hacer click en mapa → buscar todos los PuntoAnalisis cercanos a esa coordenada (de todas las capas activas) → mostrar panel con todas las variables comparadas (valor del punto, valor máximo, diferencia).

**Why:** El usuario quiere poder subir análisis de suelo, NDVI, rendimiento histórico como capas independientes y cruzarlas visualmente en el mapa al hacer click en cualquier punto.
**How to apply:** Diseñar modelos con FK a Campo + CicloAgricola opcional + fecha del análisis. Query espacial por proximidad al punto clickeado.

### 9. Planejamento Safra (PRIORIDAD A DEFINIR)
Planificación de la cosecha/zafra — presupuesto y proyección antes de iniciar el ciclo.
- Probablemente: planificar insumos, costos y rendimiento esperado por lote/ciclo antes de ejecutar
- Ver más pantallas para definir alcance

### 8. Agricultura / Atividades Agrícolas (BrazSoft) — YA LO TENEMOS bajo otro enfoque
BrazSoft tiene: Talhão Padrão, Ciclos de Produção, Talhões Ciclo Produção, Lançamentos de Atividades, Custo Administrativo, Fechamento de Safra.

La lista de actividades muestra: Código, Ficha, Fecha, Actividad, Área, Ciclo de Producción, Talhão, Valor Total, Valor Total Dólar.

Desde cada actividad se puede abrir: **Pragas, Trabalho de Máquinas, Recomendação Insumos, Aplicação Insumos, Mão de Obra, Custos Extras, Imprimir Recibo, Alterar, Excluir**.

→ **Conclusión del usuario**: "esto lo tenemos de otra forma en la gestión del talhón" — no es prioridad replicar, ya está cubierto en new_agro con el flujo de ciclos/fases/actividades.

### 7. Departamento Pessoal — BAJA PRIORIDAD (el usuario lo descartó por ahora)
- Funcionários, Folhas de Pagamento

### 11. Producción — módulo completo
Entradas de Producción, Transferencia, Compra/Venta, Saídas de Producción, Comercialización Directa, Tabla de Fletes, Fletes.
Dashboard con filtro por Ciclo+Talhão.

### 12. Informes (Relatórios) — referencia de qué reportes hacen falta
**Controle Agrícola:**
- Resumo Custo Producción, Custo Atividades por Talhão, Resumo Producción y Custo Talhão
- Uso MO/Máquinas/Insumos por Ciclo/Talhão
- Resultado Costos por Talhão, Fechamento Safra, Custo Administrativo
- **Planejamento Safra X Realizado** ← muy importante, comparar presupuesto vs real
- Contrato Comercialización Futuros, Entregas, Comercialización Directa
- Producción: Entrada/Salida, Stock, Productividad, Resultado, Pesagem Avulsa, Colheita, Transferencia

**Controle Estoque:** Entrada/Salida materiales, Resumo Estoque, por Fornecedor, Orden Compra, Cotação Comparativa, etc.

**Controle Máquina:** Consumo Insumo por Máquina, Custo Manutenção, Máquina x Custos.

### 13. Dashboard financiero avanzado
Gráficos: Contas a Pagar/Receber por Mes (diario), Fluxo Financeiro Previsto vs Realizado (Crédito/Débito/Saldo), Abastecimento de Máquinas Mensal.

### 14. Registro de Clima — PRIORIDAD BAJA
Registro diario de clima vinculado a la fazenda.

### 15. Manifesto de Documentos (SEFAZ)
Manifestación de ciência/confirmação sobre NFe/CTe recibidas — parte del flujo SEFAZ.

**Why:** El usuario quiere replicar la parte agrícola de BrazSoft, especialmente el análisis de costos por lote, gestión fiscal automatizada y módulo financiero integrado con cuentas bancarias.
**How to apply:** Cuando el usuario pida implementar alguna de estas features, referirse a este contexto y prioridades. El usuario irá mostrando más pantallas de referencia.
