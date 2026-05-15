/* ============================================================
   charts.js — Company detail page runtime
   - fetch data.json → fill [data-bind] + render charts
   - Chart.js is loaded via /assets/vendor/chart.umd.min.js
   ============================================================ */

const CURRENCY_SYMBOL = { USD: "$", JPY: "¥", HKD: "HK$", CNY: "¥", EUR: "€" };
const COMPACT = { USD: { div: 1e9, suffix: "B" },
                  JPY: { div: 1e12, suffix: "兆" },
                  HKD: { div: 1e9, suffix: "B" },
                  CNY: { div: 1e9, suffix: "B" },
                  EUR: { div: 1e9, suffix: "B" } };

function fmtCurrency(value, currency = "USD", maxFractionDigits = 2) {
  if (value == null || Number.isNaN(value)) return "—";
  const symbol = CURRENCY_SYMBOL[currency] || currency + " ";
  return symbol + Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxFractionDigits,
  });
}

function fmtCompactCurrency(value, currency = "USD") {
  if (value == null) return "—";
  const c = COMPACT[currency] || COMPACT.USD;
  const v = Number(value) / c.div;
  const symbol = CURRENCY_SYMBOL[currency] || currency + " ";
  return symbol + v.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }) + " " + c.suffix;
}

function fmtPercent(value, digits = 1) {
  if (value == null || Number.isNaN(value)) return "—";
  return (Number(value) * 100).toFixed(digits) + "%";
}

function fmtMultiple(value, digits = 1) {
  if (value == null || Number.isNaN(value)) return "—";
  return Number(value).toFixed(digits) + "x";
}

function fmtRange(low, high, currency = "USD") {
  if (low == null || high == null) return "—";
  return `${fmtCurrency(low, currency, 0)} – ${fmtCurrency(high, currency, 0)}`;
}

function fmtUpdatedAt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

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

/* ---- Market data fill ---- */
function fillMarketData(snapshot, updatedAt, mockMode = false) {
  if (!snapshot) return;
  const c = snapshot.currency || "USD";

  setBind("price", fmtCurrency(snapshot.price, c, 2));
  setBind("market-cap", fmtCompactCurrency((snapshot.market_cap_b || 0) * 1e9, c));
  setBind("ev", fmtCompactCurrency((snapshot.ev_b || 0) * 1e9, c));
  setBind("pe-forward", fmtMultiple(snapshot.pe_forward));
  setBind("pb", fmtMultiple(snapshot.pb));
  setBind("revenue-growth-ttm", fmtPercent(snapshot.revenue_growth_ttm));
  setBind("operating-margin", fmtPercent(snapshot.operating_margin));
  setBind("net-margin", fmtPercent(snapshot.net_margin));
  setBind("week52-range", fmtRange(snapshot.week52_low, snapshot.week52_high, c));
  setBind("analyst-target", fmtCurrency(snapshot.analyst_target_median, c, 0));
  setBind("updated-at", fmtUpdatedAt(updatedAt));

  if (mockMode) {
    document.querySelectorAll("[data-bind-mock-badge]").forEach((el) => {
      el.removeAttribute("hidden");
    });
  }
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
  return {
    type: "line",
    data: {
      labels: series.dates,
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
    options: commonChartOptions({ yLeftTitle: "" }),
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

function commonChartOptions({ yLeftTitle = "" } = {}) {
  return {
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
          autoSkipPadding: 32,
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
        title: { display: !!yLeftTitle, text: yLeftTitle, color: TICK },
      },
    },
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

/* ---- Entry point ---- */
async function loadCompanyData(ticker) {
  fillMeta();
  try {
    const res = await fetch("./data.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    fillMarketData(data.snapshot, data.updated_at, !!data.mock_data);
    renderChart("price-10y", buildPriceChart(data.charts && data.charts.price_10y));
    renderChart("per-pbr-10y", buildPerPbrChart(data.charts && data.charts.per_pbr_10y));
  } catch (err) {
    console.error("loadCompanyData failed for", ticker, err);
    setBind("updated-at", "数据加载失败");
  }
}

window.loadCompanyData = loadCompanyData;
