---
name: project-artuarium
description: "Estado actual de artuarium_new — sistema completo de partners, tracking, reservas, comisiones y pagos"
metadata: 
  node_type: memory
  type: project
  originSessionId: 77cbae1d-7455-4787-a707-e3167571e780
---

## Proyecto activo: `artuarium_new`

Ruta: `/home/diego/Work/Django/artuarium_new/core/`  
**Stack:** Django 5.2, SQLite (dev) / MySQL (prod PythonAnywhere), dominio `artuarium.global`  
**Una sola app activa:** `landing` — todo vive ahí (modelos, vistas, forms, urls, admin)

---

## Modelos (`landing/models.py`)

- `Usuario(AbstractUser)` — tipos: admin / partner / guia
- `Partner` — codigo, codigo_pagina, landing_code, tracking_token, comision_default, qr_image
- `Tour` — bokun_id, bokun_widget_url, is_featured, is_active
- `Reserva` — bokun_id único, partner FK null, tour FK null, cliente, monto, external_ref
- `Comision` — reserva OneToOne, partner, pago FK null, tasa_aplicada, monto, estado
- `Pago` — partner, fecha_pago, monto_pagado, numero_comprobante (REC-YYYY-NNNN auto), comprobante FileField, comentario
- `Reputacion`, `NewsletterSubscriber`

---

## Flujo de tracking completo

1. Partner creado → auto-genera usuario, password, QR, landing_code, tracking_token
2. QR apunta a `/en/landing/{landing_code}/?t={tracking_token}`
3. `partner_landing` valida token → setea cookie `artu_ref` firmada con `signing.dumps(partner.pk)` → redirect al index
4. `index` lee cookie → `signing.dumps(codigo_pagina, salt='artuarium.bokun_ref')` → `external_ref` al template
5. Botones Bokun llevan `&externalRef={signed_value}`
6. Bokun webhook: `POST /api/redemption/?token={BOKUN_WEBHOOK_SECRET}` → valida → `signing.loads(externalRef)` → crea `Reserva` + `Comision`

---

## URLs clave (`landing/urls.py` bajo `/en/dashboard/`)

- `promociones` — dashboard admin principal
- `partner_list/create/update/delete`
- `tour_create/update/toggle-active/set-featured`
- `sync-bokun/` — sincroniza tours desde Bokun API
- `pagos/{pk}/` — lista comisiones con checkboxes
- `pagos/{pk}/registrar/` — form de pago (auto: número, fecha, monto)
- `pagos/recibo/{pk}/` — recibo imprimible
- `cuenta/{pk}/` — cuenta corriente por partner (ledger cronológico)
- `mi-panel/` — dashboard del partner

---

## Dashboard admin

- 4 tabs: Resumen / Partners / Tours / Comisiones
- Tab Comisiones: pendientes por partner + historial de pagos (ambos con acordeón)
- Tab Resumen: Rendimiento por partner + Historial de reservas (ambos con acordeón)

## Dashboard partner

- KPIs: Total comisión / Total recibido / Pendiente
- Acordeones: "Mi QR y link de referido" / "Mis comisiones" / "Pagos recibidos"
- QR descargable + link de referido + snippet HTML con botón copiar

---

## Credenciales dev

- Admin: `admin` / `admin1234`
- Partner test: `hotel-beira-rio` / `Beira2025!`
- Partner test: `diego-1` / `Diego2025!`

---

## Settings clave

- `AUTH_USER_MODEL = 'landing.Usuario'`
- `LOGIN_URL = 'login'`
- `BOKUN_API_KEY`, `BOKUN_SECRET`, `BOKUN_CHANNEL_UUID`, `BOKUN_WEBHOOK_SECRET` — en settings.py
- `MEDIA_URL = '/media/'`
