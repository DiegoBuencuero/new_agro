$(function () {

  const tileMapa = L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    { maxZoom: 20 }
  );

  const mapa = L.map('mapa', {
    center: [-27.45, -51.22],
    zoom: 14,
    layers: [tileMapa],
    preferCanvas: true
  });

  window.mapa = mapa;

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

    if (!campoId) return;

    cargarListaCapas(campoId);
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

    $('#modalLat').text(latlng.lat.toFixed(6));
    $('#modalLng').text(latlng.lng.toFixed(6));

    let rows = '';

    resultados.forEach(r => {

      const v = Number(r.feature.properties.v);

      rows += `
        <tr>
          <td>${r.info.nombre}</td>
          <td>${r.info.variable}</td>
          <td>${v.toFixed(2)}</td>
          <td>${r.info.valor_promedio.toFixed(2)}</td>
          <td>${r.info.valor_max.toFixed(2)}</td>
          <td>${r.info.valor_min.toFixed(2)}</td>
        </tr>
      `;
    });

    $('#tablaPropsPunto').html(rows);

    bootstrap.Modal.getOrCreateInstance(document.getElementById('infoModal')).show();
  }

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