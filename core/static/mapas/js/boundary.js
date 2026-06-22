/**
 * boundary.js — gestión completa del contorno del campo.
 *
 * Estados del panel:
 *   vacio      → sin contorno, botones dibujar/shapefile
 *   confirmar  → polígono dibujado, pendiente guardar
 *   existente  → contorno guardado, muestra ha + editar/eliminar
 *   editando   → modo edición Leaflet.draw activo
 */
(function () {
  "use strict";

  // ── Estado interno ────────────────────────────────────────────────
  let drawControl      = null;
  let editControl      = null;
  let boundaryLayer    = null;
  let pendingLayer     = null;   // polígono dibujado, aún no guardado
  const drawnItems     = new L.FeatureGroup();

  function map()      { return window.mapa; }
  function campoId()  { return document.getElementById("select-campo")?.value || null; }
  function url(base, id) { return base.replace("/0/", `/${id}/`); }

  // ── Calcular hectáreas (geodésico) ────────────────────────────────
  function calcularHa(layer) {
    try {
      const latlngs = layer.getLatLngs()[0];
      const area    = L.GeometryUtil.geodesicArea(latlngs); // m²
      return (area / 10000).toFixed(2);
    } catch { return "—"; }
  }

  // ── Paneles de UI ─────────────────────────────────────────────────
  const paneles = ["vacio", "confirmar", "existente", "editando"];

  function mostrarPanel(cual) {
    paneles.forEach(p => {
      const el = document.getElementById(`boundary-panel-${p}`);
      if (el) el.style.display = p === cual ? "block" : "none";
    });
    const sec = document.getElementById("section-boundary");
    if (sec) sec.style.display = "block";
  }

  function setAreaDisplay(ha, elementId) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = ha !== "—" ? `${ha} ha` : "—";
  }

  // ── Mostrar boundary en mapa ──────────────────────────────────────
  function mostrarBoundary(geojson) {
    limpiarBoundary();
    boundaryLayer = L.geoJSON(geojson, {
      style: { color: "#2e7d32", weight: 2.5, fillOpacity: 0.06, dashArray: "6 4" },
    }).addTo(map());
    boundaryLayer.eachLayer(l => drawnItems.addLayer(l));
    map().fitBounds(boundaryLayer.getBounds(), { padding: [30, 30] });

    // Calcular ha desde la primera capa
    const ha = boundaryLayer.getLayers().length
      ? calcularHa(boundaryLayer.getLayers()[0])
      : "—";
    setAreaDisplay(ha, "boundary-area-display");
    mostrarPanel("existente");
  }

  function limpiarBoundary() {
    if (boundaryLayer) { map().removeLayer(boundaryLayer); boundaryLayer = null; }
    drawnItems.clearLayers();
  }

  function limpiarPendiente() {
    if (pendingLayer) { map().removeLayer(pendingLayer); pendingLayer = null; }
    if (drawControl)  { map().removeControl(drawControl);  drawControl = null; }
    map().off("draw:created").off("draw:drawstop");
  }

  function cancelarEdicion() {
    if (editControl) {
      editControl.disable();
      editControl = null;
    }
    // Restaurar visual del boundary original
    if (boundaryLayer) mostrarBoundary(JSON.parse(JSON.stringify(boundaryLayer.toGeoJSON())));
  }

  // ── Cargar boundary existente ─────────────────────────────────────
  function cargarBoundary(id) {
    limpiarBoundary();
    fetch(url(window.MAPA_URLS.getBoundary, id))
      .then(r => r.json())
      .then(res => {
        if (res.ok && res.geojson) {
          mostrarBoundary(res.geojson);
        } else {
          mostrarPanel("vacio");
        }
      });
  }

  // ── Guardar en servidor ───────────────────────────────────────────
  function guardarBoundary(id, geojson, onSuccess) {
    fetch(url(window.MAPA_URLS.guardarBoundary, id), {
      method:  "POST",
      headers: { "X-CSRFToken": window.CSRF_TOKEN, "Content-Type": "application/json" },
      body:    JSON.stringify({ geojson }),
    })
      .then(r => r.json())
      .then(res => {
        if (res.ok) onSuccess();
        else alert("Error al guardar: " + res.error);
      });
  }

  // ── Iniciar dibujo ────────────────────────────────────────────────
  function iniciarDibujo() {
    const m = map();
    if (!m.hasLayer(drawnItems)) m.addLayer(drawnItems);
    limpiarPendiente();
    limpiarBoundary();

    drawControl = new L.Control.Draw({
      draw: {
        polygon: {
          allowIntersection: false,
          showArea: true,
          metric: true,
          shapeOptions: { color: "#1565c0", fillOpacity: 0.08, dashArray: null },
        },
        polyline: false, circle: false, circlemarker: false,
        marker: false, rectangle: false,
      },
      edit: { featureGroup: drawnItems, remove: false },
    });
    m.addControl(drawControl);
    mostrarPanel("confirmar");
    setAreaDisplay("—", "boundary-area-preview");
    document.getElementById("btn-guardar-boundary").disabled = true;

    // Actualizar área en tiempo real mientras dibuja
    m.on("draw:drawvertex", function () {
      // leaflet-draw no expone polígono parcial fácilmente, usamos el handler
      try {
        const handler = drawControl._toolbars.draw._modes.polygon.handler;
        if (handler && handler._poly) {
          const lls = handler._poly.getLatLngs();
          if (lls.length >= 3) {
            const tmpArea = L.GeometryUtil.geodesicArea(lls);
            setAreaDisplay((tmpArea / 10000).toFixed(2), "boundary-area-preview");
          }
        }
      } catch { /* noop */ }
    });

    m.off("draw:created").on("draw:created", function (e) {
      pendingLayer = e.layer;
      drawnItems.clearLayers();
      drawnItems.addLayer(pendingLayer);
      m.removeControl(drawControl); drawControl = null;
      m.off("draw:drawvertex");

      const ha = calcularHa(pendingLayer);
      setAreaDisplay(ha, "boundary-area-preview");
      document.getElementById("btn-guardar-boundary").disabled = false;
    });

    // Si cancela el dibujo con Escape
    m.off("draw:drawstop").on("draw:drawstop", function () {
      if (!pendingLayer) {
        // Volvió a cancelar sin completar
        if (boundaryLayer) mostrarPanel("existente");
        else mostrarPanel("vacio");
      }
    });
  }

  // ── Botón: Guardar contorno (tras dibujar) ────────────────────────
  document.getElementById("btn-guardar-boundary")?.addEventListener("click", function () {
    const id = campoId();
    if (!id || !pendingLayer) return;
    const geojson = drawnItems.toGeoJSON();
    guardarBoundary(id, geojson, () => {
      pendingLayer = null;
      drawnItems.clearLayers();
      mostrarBoundary(geojson);
    });
  });

  // ── Botón: Cancelar dibujo ────────────────────────────────────────
  document.getElementById("btn-descartar-boundary")?.addEventListener("click", function () {
    limpiarPendiente();
    if (boundaryLayer) {
      mostrarPanel("existente");
    } else {
      drawnItems.clearLayers();
      mostrarPanel("vacio");
    }
  });

  // ── Botón: Dibujar ────────────────────────────────────────────────
  document.getElementById("btn-dibujar-boundary")?.addEventListener("click", iniciarDibujo);
  document.getElementById("btn-redibujar-boundary")?.addEventListener("click", iniciarDibujo);

  // ── Botón: Editar contorno existente ─────────────────────────────
  document.getElementById("btn-editar-boundary")?.addEventListener("click", function () {
    if (!boundaryLayer) return;
    const m = map();
    if (!m.hasLayer(drawnItems)) m.addLayer(drawnItems);

    // Sincronizar drawnItems con el boundary actual
    drawnItems.clearLayers();
    boundaryLayer.eachLayer(l => {
      const clone = L.geoJSON(l.toGeoJSON(), {
        style: { color: "#1565c0", weight: 2, fillOpacity: 0.08 },
      });
      clone.eachLayer(cl => drawnItems.addLayer(cl));
    });
    m.removeLayer(boundaryLayer);

    editControl = new L.EditToolbar.Edit(m, { featureGroup: drawnItems });
    editControl.enable();
    mostrarPanel("editando");
  });

  // ── Botón: Guardar edición ────────────────────────────────────────
  document.getElementById("btn-guardar-edicion")?.addEventListener("click", function () {
    if (!editControl) return;
    editControl.save();
    editControl.disable();
    editControl = null;

    const id      = campoId();
    const geojson = drawnItems.toGeoJSON();
    guardarBoundary(id, geojson, () => mostrarBoundary(geojson));
  });

  // ── Botón: Cancelar edición ───────────────────────────────────────
  document.getElementById("btn-cancelar-edicion")?.addEventListener("click", function () {
    cancelarEdicion();
  });

  // ── Botón: Eliminar contorno ──────────────────────────────────────
  document.getElementById("btn-eliminar-boundary")?.addEventListener("click", function () {
    if (!confirm("¿Eliminar el contorno del campo? Esta acción no se puede deshacer.")) return;
    const id = campoId();
    if (!id) return;
    fetch(url(window.MAPA_URLS.eliminarBoundary, id), {
      method:  "POST",
      headers: { "X-CSRFToken": window.CSRF_TOKEN },
    })
      .then(r => r.json())
      .then(res => {
        if (res.ok) {
          limpiarBoundary();
          mostrarPanel("vacio");
        }
      });
  });

  // ── Botón: Cargar shapefile ───────────────────────────────────────
  document.getElementById("btn-cargar-boundary-shp")?.addEventListener("click", function () {
    const id = campoId();
    if (!id) return;
    const input    = document.createElement("input");
    input.type     = "file";
    input.multiple = true;
    input.accept   = ".shp,.shx,.dbf";
    input.onchange = function () {
      const fd = new FormData();
      Array.from(input.files).forEach(f => fd.append(f.name.split(".").pop().toLowerCase(), f));
      fetch(url(window.MAPA_URLS.boundaryShp, id), {
        method:  "POST",
        headers: { "X-CSRFToken": window.CSRF_TOKEN },
        body:    fd,
      })
        .then(r => r.json())
        .then(res => {
          if (res.ok) mostrarBoundary(res.geojson);
          else alert("Error: " + res.error);
        });
    };
    input.click();
  });

  // ── Reset completo del estado de boundary ─────────────────────────
  function resetTodo() {
    // 1. Cancelar edit si está activo
    if (editControl) {
      try { editControl.revertLayers(); editControl.disable(); } catch { /* noop */ }
      editControl = null;
    }
    // 2. Cancelar draw si está activo
    if (drawControl) {
      try {
        // Forzar fin del handler de dibujo activo
        const toolbar = drawControl._toolbars && drawControl._toolbars.draw;
        if (toolbar && toolbar._activeMode) toolbar._activeMode.handler.disable();
        map().removeControl(drawControl);
      } catch { /* noop */ }
      drawControl = null;
    }
    // 3. Limpiar capas
    map().off("draw:created").off("draw:drawstop").off("draw:drawvertex");
    limpiarPendiente();
    limpiarBoundary();
    pendingLayer = null;
  }

  // ── Al cambiar campo ──────────────────────────────────────────────
  document.getElementById("select-campo")?.addEventListener("change", function () {
    const id = this.value;
    resetTodo();
    const sec = document.getElementById("section-boundary");
    if (id) {
      sec.style.display = "block";
      cargarBoundary(id);
    } else {
      sec.style.display = "none";
    }
  });

})();
