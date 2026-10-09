// Gráficas de serie temporal con Chart.js (vendorizado en /static/vendor).
// Una sola escala Y por gráfica; umbrales como líneas discontinuas con su leyenda.
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function formatoHora(ms) {
  return new Date(ms).toLocaleTimeString("es-GT", { hour12: false });
}

export function lineaTiempo(canvas, { series, umbrales = [], unidad = "", yMin, yMax, ventanaMin = 15 }) {
  const Chart = window.Chart;
  const ventana = ventanaMin * 60 * 1000;
  const datasets = series.map((s) => ({
    label: s.etiqueta, _clave: s.clave, data: [], borderColor: css(s.color), backgroundColor: css(s.color),
    borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.25,
  }));
  for (const u of umbrales) {
    datasets.push({
      label: u.etiqueta, _umbral: u.valor, data: [], borderColor: css(u.color), borderWidth: 1.5,
      borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 0, tension: 0,
    });
  }
  const chart = new Chart(canvas, {
    type: "line",
    data: { datasets },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false, normalized: true,
      interaction: { mode: "nearest", axis: "x", intersect: false },
      scales: {
        x: {
          type: "linear", ticks: { callback: (v) => formatoHora(v), maxTicksLimit: 6, color: css("--tenue") },
          grid: { color: css("--linea") }, border: { color: css("--eje") },
        },
        y: {
          suggestedMin: yMin, suggestedMax: yMax,
          title: { display: !!unidad, text: unidad, color: css("--tinta-2") },
          ticks: { color: css("--tenue") }, grid: { color: css("--linea") }, border: { color: css("--eje") },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          filter: (item) => item.dataset._umbral === undefined,
          callbacks: {
            title: (items) => (items.length ? formatoHora(items[0].parsed.x) : ""),
            label: (item) => `${item.dataset.label}: ${item.parsed.y.toFixed(1)} ${unidad}`,
          },
        },
      },
    },
  });

  function ajustarUmbrales() {
    let min = Infinity, max = -Infinity;
    for (const d of chart.data.datasets) {
      if (d._umbral !== undefined) continue;
      if (d.data.length) {
        min = Math.min(min, d.data[0].x);
        max = Math.max(max, d.data[d.data.length - 1].x);
      }
    }
    if (!isFinite(min)) return;
    for (const d of chart.data.datasets) {
      if (d._umbral !== undefined) d.data = [{ x: min, y: d._umbral }, { x: max, y: d._umbral }];
    }
  }

  let pendiente = false;
  function redibujar() {
    if (pendiente) return;
    pendiente = true;
    requestAnimationFrame(() => {
      pendiente = false;
      ajustarUmbrales();
      chart.update("none");
    });
  }

  return {
    chart,
    agregar(clave, x, y) {
      const d = chart.data.datasets.find((ds) => ds._clave === clave);
      if (!d || y === null || y === undefined || isNaN(y)) return;
      if (d.data.length && x <= d.data[d.data.length - 1].x) return;
      d.data.push({ x, y });
      const corte = x - ventana;
      while (d.data.length && d.data[0].x < corte) d.data.shift();
      redibujar();
    },
    fijarUmbral(etiqueta, valor) {
      const d = chart.data.datasets.find((ds) => ds.label === etiqueta);
      if (d) { d._umbral = valor; redibujar(); }
    },
  };
}
