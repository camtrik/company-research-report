/* ============================================================
   charts.js — Company detail page runtime
   - fetch data.json → render price chart
   - fetch per_pbr.json → render PER/PBR chart + update timestamp
   - Chart.js is loaded via /assets/vendor/chart.umd.min.js
   ============================================================ */

/* ---- DOM helpers ---- */
function setBind(name, value) {
  document.querySelectorAll(`[data-bind="${name}"]`).forEach((el) => {
    if (value == null || value === "") {
      el.textContent = "—";
    } else {
      el.textContent = value;
    }
  });
}

/* ---- Header meta fill (from <meta data-region="meta">) ---- */
function fillMeta() {
  const meta = document.querySelector('meta[data-region="meta"]');
  if (!meta) return;
  setBind("ticker", meta.dataset.ticker || "");
  setBind("name", meta.dataset.name || "");
  setBind("name-en", meta.dataset.nameEn || "");
  setBind("market", meta.dataset.market || "");
  setBind("sector", meta.dataset.sector || "");
  setBind("view", meta.dataset.view || "");
  setBind("last-updated", meta.dataset.lastUpdated || "");

  const tagsRow = document.querySelector('[data-bind="tags-row"]');
  if (tagsRow && meta.dataset.tags) {
    tagsRow.innerHTML = "";
    meta.dataset.tags.split(",").map((t) => t.trim()).filter(Boolean).forEach((tag) => {
      const pill = document.createElement("span");
      pill.className = "pill pill--ghost";
      pill.textContent = "#" + tag;
      tagsRow.appendChild(pill);
    });
  }
}

/* ---- Chart configs ---- */
const INK = "#141413";
const ACCENT = "#CF4500";
const ACCENT_LIGHT = "#F37338";
const GRID = "rgba(20, 20, 19, 0.08)";
const TICK = "#696969";
const FONT = "Sofia Sans, Arial, sans-serif";

function buildPriceChart(series) {
  if (!series || !series.dates || !series.values) return null;
  const fullDates = series.dates;
  return {
    type: "line",
    data: {
      labels: fullDates,
      datasets: [{
        label: "Price",
        data: series.values,
        borderColor: INK,
        borderWidth: 1.6,
        backgroundColor: "rgba(20, 20, 19, 0.04)",
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: ACCENT,
        pointHoverBorderColor: INK,
        tension: 0.18,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: INK,
          titleColor: "#F3F0EE",
          bodyColor: "#F3F0EE",
          cornerRadius: 8,
          padding: 10,
          callbacks: {
            title: function(items) {
              return fullDates[items[0].dataIndex];
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: TICK,
            font: { family: FONT, size: 11 },
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 12,
            callback: function(value, index) {
              var label = this.getLabelForValue(value);
              return label ? label.substring(0, 4) : "";
            },
          },
          border: { display: false },
        },
        y: {
          grid: { color: GRID, drawTicks: false },
          ticks: {
            color: TICK,
            font: { family: FONT, size: 11 },
            padding: 8,
          },
          border: { display: false },
        },
      },
    },
  };
}

function buildPerPbrChart(series) {
  if (!series || !series.years) return null;
  return {
    type: "line",
    data: {
      labels: series.years.map(String),
      datasets: [
        {
          label: "PER",
          data: series.per,
          yAxisID: "yPer",
          borderColor: INK,
          borderWidth: 1.6,
          backgroundColor: "transparent",
          pointRadius: 3,
          pointBackgroundColor: INK,
          pointHoverBackgroundColor: ACCENT,
          tension: 0.18,
        },
        {
          label: "PBR",
          data: series.pbr,
          yAxisID: "yPbr",
          borderColor: ACCENT_LIGHT,
          borderWidth: 1.6,
          backgroundColor: "transparent",
          pointRadius: 3,
          pointBackgroundColor: ACCENT_LIGHT,
          pointHoverBackgroundColor: ACCENT,
          borderDash: [4, 4],
          tension: 0.18,
        },
      ],
    },
    options: dualAxisChartOptions(),
  };
}

function dualAxisChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        display: true,
        position: "top",
        align: "end",
        labels: {
          color: INK,
          font: { family: FONT, size: 12, weight: "500" },
          usePointStyle: true,
          boxWidth: 10,
        },
      },
      tooltip: {
        backgroundColor: INK,
        titleColor: "#F3F0EE",
        bodyColor: "#F3F0EE",
        cornerRadius: 8,
        padding: 10,
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: TICK, font: { family: FONT, size: 11 } },
        border: { display: false },
      },
      yPer: {
        type: "linear",
        position: "left",
        grid: { color: GRID, drawTicks: false },
        ticks: {
          color: TICK,
          font: { family: FONT, size: 11 },
          callback: (v) => v + "x",
        },
        border: { display: false },
        title: { display: true, text: "PER", color: TICK, font: { family: FONT, size: 11 } },
      },
      yPbr: {
        type: "linear",
        position: "right",
        grid: { display: false },
        ticks: {
          color: TICK,
          font: { family: FONT, size: 11 },
          callback: (v) => v + "x",
        },
        border: { display: false },
        title: { display: true, text: "PBR", color: TICK, font: { family: FONT, size: 11 } },
      },
    },
  };
}

function renderChart(chartKey, config) {
  if (!config) return;
  const canvas = document.querySelector(`canvas[data-chart="${chartKey}"]`);
  if (!canvas) return;
  if (typeof Chart === "undefined") {
    console.warn("Chart.js not loaded yet");
    return;
  }
  if (canvas._chartInstance) canvas._chartInstance.destroy();
  canvas._chartInstance = new Chart(canvas, config);
}

/* ---- PER/PBR history table (rendered from per_pbr.json) ---- */
function renderPerPbrTable(series) {
  const tbody = document.querySelector('[data-bind="per-pbr-table"]');
  if (!tbody || !series || !Array.isArray(series.years)) return;
  const {
    years,
    year_end_price = [],
    eps = [],
    bps = [],
    per = [],
    pbr = [],
  } = series;

  const fmt = (v, digits) => {
    if (v == null || Number.isNaN(v)) return "—";
    if (digits != null) return Number(v).toFixed(digits);
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
  };

  tbody.innerHTML = years.map((y, i) => `
    <tr>
      <td>FY${y}</td>
      <td class="num">${fmt(year_end_price[i])}</td>
      <td class="num">${fmt(eps[i], 2)}</td>
      <td class="num">${fmt(bps[i])}</td>
      <td class="num">${fmt(per[i], 1)}</td>
      <td class="num">${fmt(pbr[i], 1)}</td>
    </tr>
  `).join("");
}

/* ---- Entry point ---- */
async function loadCompanyData(ticker) {
  fillMeta();
  try {
    const res = await fetch("./data.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderChart("price-10y", buildPriceChart(data.charts && data.charts.price_10y));
  } catch (err) {
    console.error("data.json load failed for", ticker, err);
  }
  try {
    const res = await fetch("./per_pbr.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderChart("per-pbr-10y", buildPerPbrChart(data.per_pbr_10y));
    renderPerPbrTable(data.per_pbr_10y);
    if (data.updated_at) {
      setBind("per-pbr-updated", data.updated_at.substring(0, 10));
    }
  } catch (err) {
    console.warn("per_pbr.json not available for", ticker);
  }
}

window.loadCompanyData = loadCompanyData;
