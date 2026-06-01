$(function () {

  const tileMapa = L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    { maxZoom: 20 }
  );

  const tileSatelite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 20, attribution: 'Esri World Imagery' }
  );

  const mapa = L.map('mapa', {
    center: [-27.45, -51.22],
    zoom: 14,
    layers: [tileMapa],
    preferCanvas: true
  });

  window.mapa = mapa;

  // ── Toggle Mapa / Satélite ───────────────────────────────────────
  $('#btn-vista-mapa').on('click', function () {
    if (!mapa.hasLayer(tileMapa)) {
      mapa.removeLayer(tileSatelite);
      mapa.addLayer(tileMapa);
    }
    $('#btn-vista-mapa').addClass('btn-success').removeClass('btn-outline-secondary');
    $('#btn-vista-satelite').removeClass('btn-success').addClass('btn-outline-secondary');
  });

  $('#btn-vista-satelite').on('click', function () {
    if (!mapa.hasLayer(tileSatelite)) {
      mapa.removeLayer(tileMapa);
      mapa.addLayer(tileSatelite);
    }
    $('#btn-vista-satelite').addClass('btn-success').removeClass('btn-outline-secondary');
    $('#btn-vista-mapa').removeClass('btn-success').addClass('btn-outline-secondary');
  });

  // ── Centrar en capas activas ─────────────────────────────────────
  $('#btn-fit-bounds').on('click', function () {
    const capas = Object.values(state.capasActivas).map(c => c.layer);
    if (capas.length === 0) return;
    const group = L.featureGroup(capas);
    mapa.fitBounds(group.getBounds(), { padding: [20, 20] });
  });

  const state = {
    capasActivas: {},
    campoActual: null,
  };

  // ============================
  // SELECT CAMPO
  // ============================

  $('#select-campo').on('change', function () {
    const campoId = $(this).val();

    state.campoActual = campoId || null;

    Object.keys(state.capasActivas).forEach(quitarCapa);
    state.capasActivas = {};
    limpiarAreas();

    $('#lista-capas').html('<p class="text-muted small mb-0">Seleccione un campo</p>');
    $('#section-areas').hide();

    if (!campoId) return;

    cargarListaCapas(campoId);
    cargarAreas(campoId);
    $('#section-areas').show();
  });

  function cargarListaCapas(campoId) {
    const url = window.MAPA_URLS.listarCapas.replace(/\/0\/$/, '/' + campoId + '/');

    $.getJSON(url, function (resp) {
      renderListaCapas(resp.capas || []);
    });
  }

  function renderListaCapas(capas) {
    window.__capasInfo = {};
    let html = '';

    capas.forEach(function (c) {
      html += `
        <div class="capa-item">
          <input type="checkbox" class="chk-capa" data-id="${c.id}">
          ${c.nombre}
        </div>
      `;
      window.__capasInfo[c.id] = c;
    });

    $('#lista-capas').html(html);
  }

  // ============================
  // ACTIVAR CAPA
  // ============================

  $(document).on('change', '.chk-capa', function () {
    const id = $(this).data('id');

    if (this.checked) {
      mostrarCapa(id);
    } else {
      quitarCapa(id);
    }
  });

  function mostrarCapa(id) {
    const info = window.__capasInfo[id];

    $.getJSON(info.geojson_url, function (geojson) {

      const layer = L.geoJSON(geojson, {
        renderer: L.canvas(),
        style: f => ({
          color: '#fff',
          weight: 0.3,
          fillColor: colorEscala(f.properties.v, info.valor_min, info.valor_max),
          fillOpacity: 0.8
        })
      }).addTo(mapa);

      state.capasActivas[id] = {
        layer: layer,
        info: info,
        geojson: geojson
      };

      mapa.fitBounds(layer.getBounds());
    });
  }

  function quitarCapa(id) {
    const c = state.capasActivas[id];
    if (!c) return;

    mapa.removeLayer(c.layer);
    delete state.capasActivas[id];
  }

  // ============================
  // CLICK GLOBAL (CLAVE)
  // ============================

  mapa.on('click', function (e) {

    const resultados = [];

    Object.values(state.capasActivas).forEach(function (capa) {

      const f = buscarFeature(capa.geojson, e.latlng);

      if (f) {
        resultados.push({
          feature: f,
          info: capa.info
        });
      }
    });

    if (!resultados.length) return;

    mostrarModal(resultados, e.latlng);
  });

  // ============================
  // BUSCAR POLIGONO
  // ============================

  function buscarFeature(geojson, latlng) {

    const x = latlng.lng;
    const y = latlng.lat;

    for (const f of geojson.features) {

      const coords = f.geometry.coordinates[0];

      if (puntoEnPoligono([x, y], coords)) {
        return f;
      }
    }

    return null;
  }

  function puntoEnPoligono(p, poly) {
    let inside = false;

    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i][0], yi = poly[i][1];
      const xj = poly[j][0], yj = poly[j][1];

      const intersect =
        ((yi > p[1]) !== (yj > p[1])) &&
        (p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi);

      if (intersect) inside = !inside;
    }

    return inside;
  }

  // ============================
  // MODAL
  // ============================

  function mostrarModal(resultados, latlng) {
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('infoModal'));

    // Reset estado
    $('#analisis-loading').show();
    $('#analisis-contenido').hide();
    $('#modalLat').text(latlng.lat.toFixed(6));
    $('#modalLng').text(latlng.lng.toFixed(6));
    $('#analisis-coords-footer').text('Lat ' + latlng.lat.toFixed(6) + '  Lng ' + latlng.lng.toFixed(6));
    modal.show();

    if (!state.campoActual) return;

    const url = window.MAPA_URLS.analisisPunto.replace('/0/', '/' + state.campoActual + '/');

    $.getJSON(url + '?lat=' + latlng.lat + '&lng=' + latlng.lng, function (d) {
      $('#analisis-loading').hide();
      $('#analisis-contenido').show();

      // ── Dados de Plantío ──────────────────────────────
      if (d.ciclo) {
        $('#pt-cultivo').text(d.ciclo.cultivo || '—');
        $('#pt-variedad').text(d.ciclo.variedad || '—');
        $('#pt-fecha').text(d.ciclo.fecha_inicio || '—');
        $('#pt-superficie').text(d.ciclo.superficie ? d.ciclo.superficie + ' ha' : '—');
        $('#bloque-plantio').show();
      } else {
        $('#bloque-plantio').hide();
      }

      // ── Rendimento ────────────────────────────────────
      const rend = d.rendimiento;
      if (rend && rend.punto !== null) {
        const u = rend.unidad || 'kg/ha';
        $('#rend-punto').text(rend.punto + ' ' + u);
        $('#rend-max').text(rend.maximo !== null ? rend.maximo + ' ' + u : '—');
        $('#rend-prom').text(rend.promedio !== null ? rend.promedio + ' ' + u : '—');
        $('#rend-min').text(rend.minimo !== null ? rend.minimo + ' ' + u : '—');
        $('#bloque-rendimiento').show();
      } else {
        $('#bloque-rendimiento').hide();
      }

      // ── Variables analíticas ──────────────────────────
      const vars = d.variables || [];
      if (vars.length === 0) {
        $('#tabla-variables').hide();
        $('#sin-variables').show();
        $('#analisis-sin-datos').toggle(!d.ciclo && rend.punto === null);
      } else {
        $('#sin-variables').hide();
        $('#analisis-sin-datos').hide();
        let rows = '';
        vars.forEach(function (v) {
          const dif = v.diferencia;
          let difHtml = '—';
          if (dif !== null && dif !== undefined) {
            const color = dif >= 0 ? '#198754' : '#dc3545';
            const signo = dif >= 0 ? '+' : '';
            difHtml = '<span style="color:' + color + ';font-weight:600">' + signo + dif.toFixed(2) + '</span>';
          }
          rows += '<tr>' +
            '<td class="ps-0"><span class="fw-semibold">' + v.nombre + '</span>' +
            (v.unidad ? '<span class="text-muted ms-1" style="font-size:.72rem">(' + v.unidad + ')</span>' : '') +
            '</td>' +
            '<td class="text-end fw-bold">' + v.valor.toFixed(2) + '</td>' +
            '<td class="text-end text-muted">' + (v.val_max !== null ? v.val_max.toFixed(2) : '—') + '</td>' +
            '<td class="text-end">' + difHtml + '</td>' +
            '</tr>';
        });
        $('#tbody-variables').html(rows);
        $('#tabla-variables').show();
      }

    }).fail(function () {
      $('#analisis-loading').hide();
      $('#analisis-contenido').show();
      $('#analisis-sin-datos').show();
    });
  }

  // ============================
  // ÁREAS DEL CAMPO
  // ============================

  const areaLayers = {};   // area_id → L.layer
  let drawControl = null;
  let layerDibujando = null;
  let areaIdEditando = null;

  function urlAreas(campoId) {
    return window.MAPA_URLS.listarAreas.replace('/0/', '/' + campoId + '/');
  }
  function urlCrearArea(campoId) {
    return window.MAPA_URLS.crearArea.replace('/0/', '/' + campoId + '/');
  }
  function urlShpArea(campoId) {
    return window.MAPA_URLS.subirAreaShp.replace('/0/', '/' + campoId + '/');
  }
  function urlGuardarGeojson(areaId) {
    return window.MAPA_URLS.guardarAreaGeojson.replace('/0/', '/' + areaId + '/');
  }
  function urlEliminarArea(areaId) {
    return window.MAPA_URLS.eliminarArea.replace('/0/', '/' + areaId + '/');
  }

  function limpiarAreas() {
    Object.values(areaLayers).forEach(l => mapa.removeLayer(l));
    Object.keys(areaLayers).forEach(k => delete areaLayers[k]);
    $('#lista-areas').html('<p class="small text-muted">Sin áreas definidas</p>');
    cancelarDibujo();
  }

  function cargarAreas(campoId) {
    $.getJSON(urlAreas(campoId), function (resp) {
      renderAreas(resp.areas || []);
    });
  }

  function renderAreas(areas) {
    Object.values(areaLayers).forEach(l => mapa.removeLayer(l));
    Object.keys(areaLayers).forEach(k => delete areaLayers[k]);

    if (!areas.length) {
      $('#lista-areas').html('<p class="small text-muted">Sin áreas definidas</p>');
      return;
    }

    let html = '';
    areas.forEach(function (a) {
      const sup = a.superficie_ha ? a.superficie_ha.toFixed(2) + ' ha' : '—';
      html += `
        <div class="area-item mb-2 p-2 border rounded" data-id="${a.id}">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <div class="fw-semibold small">${a.nombre}</div>
              <div class="text-muted" style="font-size:.75rem">${sup}</div>
            </div>
            <div class="d-flex gap-1">
              <button class="btn btn-xs btn-outline-primary btn-centrar-area" data-id="${a.id}" title="Centrar">
                <i class="mdi mdi-crosshairs-gps"></i>
              </button>
              <button class="btn btn-xs btn-outline-danger btn-eliminar-area" data-id="${a.id}" title="Eliminar">
                <i class="mdi mdi-delete"></i>
              </button>
            </div>
          </div>
        </div>`;

      if (a.geojson) {
        const layer = L.geoJSON(a.geojson, {
          style: { color: '#2d6a2d', weight: 2, fillColor: '#4caf50', fillOpacity: 0.25 }
        }).addTo(mapa);
        areaLayers[a.id] = layer;
      }
    });

    $('#lista-areas').html(html);

    const todos = Object.values(areaLayers);
    if (todos.length) {
      mapa.fitBounds(L.featureGroup(todos).getBounds(), { padding: [30, 30] });
    }
  }

  // Centrar en área
  $(document).on('click', '.btn-centrar-area', function () {
    const id = $(this).data('id');
    if (areaLayers[id]) mapa.fitBounds(areaLayers[id].getBounds(), { padding: [30, 30] });
  });

  // Eliminar área
  $(document).on('click', '.btn-eliminar-area', function () {
    const id = $(this).data('id');
    if (!confirm('¿Eliminar esta área?')) return;
    $.post({ url: urlEliminarArea(id), headers: { 'X-CSRFToken': window.CSRF_TOKEN } })
      .done(function () { cargarAreas(state.campoActual); });
  });

  // ── Dibujar nueva área ──────────────────────────────────────────────

  $('#btn-agregar-area-dibujar').on('click', function () {
    if (!state.campoActual) return;
    iniciarDibujo();
  });

  function iniciarDibujo() {
    $('#areas-panel-dibujando').show();
    $('#btn-agregar-area-dibujar, #btn-agregar-area-shp').hide();
    $('#btn-guardar-area-dibujada').prop('disabled', true);
    $('#nueva-area-nombre').val('');
    $('#nueva-area-preview').text('—');

    if (drawControl) mapa.removeControl(drawControl);
    drawControl = new L.Control.Draw({
      draw: { polygon: true, polyline: false, rectangle: false, circle: false, marker: false, circlemarker: false },
      edit: false,
    });
    mapa.addControl(drawControl);

    mapa.once('draw:created', function (e) {
      layerDibujando = e.layer;
      layerDibujando.addTo(mapa);
      const ha = L.GeometryUtil ? null : null;
      const area = calcularAreaHa(layerDibujando);
      $('#nueva-area-preview').text(area ? area.toFixed(2) + ' ha' : '—');
      $('#btn-guardar-area-dibujada').prop('disabled', false);
    });
  }

  function calcularAreaHa(layer) {
    try {
      const coords = layer.getLatLngs()[0];
      let area = 0;
      for (let i = 0, j = coords.length - 1; i < coords.length; j = i++) {
        area += (coords[j].lng + coords[i].lng) * (coords[j].lat - coords[i].lat);
      }
      const areaGrados = Math.abs(area / 2);
      return areaGrados * 111320 * 111320 * Math.cos(coords[0].lat * Math.PI / 180) / 10000;
    } catch (e) { return null; }
  }

  $('#btn-guardar-area-dibujada').on('click', function () {
    if (!layerDibujando || !state.campoActual) return;
    const nombre = $('#nueva-area-nombre').val().trim() || ('Área ' + (Object.keys(areaLayers).length + 1));
    const geojson = layerDibujando.toGeoJSON().geometry;
    const superficie = calcularAreaHa(layerDibujando);

    $.ajax({
      url: urlCrearArea(state.campoActual),
      method: 'POST',
      contentType: 'application/json',
      headers: { 'X-CSRFToken': window.CSRF_TOKEN },
      data: JSON.stringify({ nombre: nombre }),
    }).done(function (resp) {
      if (!resp.ok) return;
      $.ajax({
        url: urlGuardarGeojson(resp.id),
        method: 'POST',
        contentType: 'application/json',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        data: JSON.stringify({ geojson: geojson, superficie_ha: superficie }),
      }).done(function () {
        cancelarDibujo();
        cargarAreas(state.campoActual);
      });
    });
  });

  $('#btn-cancelar-dibujo-area').on('click', cancelarDibujo);

  function cancelarDibujo() {
    if (drawControl) { mapa.removeControl(drawControl); drawControl = null; }
    if (layerDibujando) { mapa.removeLayer(layerDibujando); layerDibujando = null; }
    $('#areas-panel-dibujando').hide();
    $('#btn-agregar-area-dibujar, #btn-agregar-area-shp').show();
  }

  // ── Shapefile de área — dropzone ────────────────────────────────────

  const archivosArea = { shp: null, shx: null, dbf: null };

  function actualizarEstadoArchivos() {
    let html = '';
    let listos = false;

    if (modoArchivo === 'kml') {
      const f = archivosArea.kml;
      const ext = f ? f.name.split('.').pop().toLowerCase() : '';
      html = `<span class="badge bg-success">.${ext} ✓ ${f ? f.name : ''}</span>`;
      listos = !!f;
    } else {
      ['shp', 'shx', 'dbf'].forEach(function (ext) {
        const ok = !!archivosArea[ext];
        html += `<span class="badge ${ok ? 'bg-success' : 'bg-secondary'}">.${ext} ${ok ? '✓' : '✗'}</span> `;
      });
      listos = !!(archivosArea.shp && archivosArea.shx && archivosArea.dbf);
    }

    $('#area-badges').html(html);
    $('#area-files-status').show();
    $('#btn-subir-area-shp').prop('disabled', !listos);
    if (listos) {
      $('#dropzone-area').css({ borderColor: '#198754', background: '#f0fff4' });
    }
  }

  let modoArchivo = null; // 'shp' | 'kml'

  function procesarArchivos(files) {
    Array.from(files).forEach(function (f) {
      const ext = f.name.split('.').pop().toLowerCase();
      if (['shp', 'shx', 'dbf'].includes(ext)) {
        archivosArea[ext] = f;
        modoArchivo = 'shp';
      } else if (['kml', 'kmz'].includes(ext)) {
        archivosArea.kml = f;
        modoArchivo = 'kml';
      }
    });
    actualizarEstadoArchivos();
  }

  // Click en dropzone abre el selector
  $('#dropzone-area').on('click', function () {
    $('#input-area-files').click();
  });

  $('#input-area-files').on('change', function () {
    procesarArchivos(this.files);
  });

  // Drag & drop — usar eventos nativos para fiabilidad
  var dropEl = document.getElementById('dropzone-area');
  dropEl.addEventListener('dragenter', function(e) { e.preventDefault(); e.stopPropagation(); });
  dropEl.addEventListener('dragover',  function(e) {
    e.preventDefault(); e.stopPropagation();
    dropEl.style.borderColor = '#0d6efd';
    dropEl.style.background  = '#f0f4ff';
  });
  dropEl.addEventListener('dragleave', function(e) {
    e.preventDefault(); e.stopPropagation();
    dropEl.style.borderColor = '#adb5bd';
    dropEl.style.background  = '';
  });
  dropEl.addEventListener('drop', function(e) {
    e.preventDefault(); e.stopPropagation();
    dropEl.style.borderColor = '#adb5bd';
    dropEl.style.background  = '';
    if (e.dataTransfer && e.dataTransfer.files.length) {
      procesarArchivos(e.dataTransfer.files);
    }
  });

  $('#btn-agregar-area-shp').on('click', function () {
    // reset
    archivosArea.shp = archivosArea.shx = archivosArea.dbf = archivosArea.kml = null;
    modoArchivo = null;
    $('#area-files-status').hide();
    $('#btn-subir-area-shp').prop('disabled', true);
    $('#dropzone-area').css({ borderColor: '#adb5bd', background: '' });
    $('#form-subir-area')[0].reset();
    $('#modalSubirArea').modal('show');
  });

  $('#form-subir-area').on('submit', function (e) {
    e.preventDefault();
    if (!state.campoActual) return;
    const nombre = $('#area-shp-nombre').val().trim() || ('Área ' + (Object.keys(areaLayers).length + 1));
    const fd = new FormData();
    fd.append('nombre', nombre);

    let url;
    if (modoArchivo === 'kml') {
      if (!archivosArea.kml) { alert('Falta el archivo KML/KMZ'); return; }
      fd.append('kml', archivosArea.kml);
      url = window.MAPA_URLS.subirAreaKml.replace('/0/', '/' + state.campoActual + '/');
    } else {
      if (!archivosArea.shp || !archivosArea.shx || !archivosArea.dbf) {
        alert('Faltan archivos (.shp, .shx, .dbf)'); return;
      }
      fd.append('shp', archivosArea.shp);
      fd.append('shx', archivosArea.shx);
      fd.append('dbf', archivosArea.dbf);
      url = urlShpArea(state.campoActual);
    }

    $.ajax({
      url: url, method: 'POST', data: fd,
      processData: false, contentType: false,
      headers: { 'X-CSRFToken': window.CSRF_TOKEN },
    }).done(function (resp) {
      if (!resp.ok) { alert('Error: ' + resp.error); return; }
      $('#modalSubirArea').modal('hide');
      cargarAreas(state.campoActual);
    }).fail(function (xhr) {
      try {
        const r = JSON.parse(xhr.responseText);
        alert('Error: ' + (r.error || xhr.responseText));
      } catch(e) {
        alert('Error ' + xhr.status + ': ' + xhr.responseText.substring(0, 200));
      }
    });
  });

  // ============================
  // COLORES
  // ============================

  function colorEscala(v, min, max) {
    const t = (v - min) / (max - min);

    if (t < 0.25) return '#1a9850';
    if (t < 0.5) return '#91cf60';
    if (t < 0.75) return '#fee08b';
    if (t < 0.9) return '#fc8d59';
    return '#d73027';
  }

});