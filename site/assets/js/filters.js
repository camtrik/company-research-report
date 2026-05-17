/* ============================================================
   filters.js — Index page company grid + search + filter
   Data source: window.COMPANIES (injected by build.py from
   each company's <meta data-region="meta">).
   Each card additionally fetches its own data.json for live price.
   ============================================================ */

const CURRENCY_SYMBOL = { USD: "$", JPY: "¥", HKD: "HK$", CNY: "¥", EUR: "€" };
const MARKET_LABEL = { US: "美股", JP: "日股", HK: "港股", CN: "A股", EU: "欧股" };
const SITE_BASE_PATH = (window.SITE_BASE_PATH || "").replace(/\/+$/, "");

const state = {
  query: "",
  market: "all",
  sector: "all",
};

function withBasePath(path) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${SITE_BASE_PATH}${normalized}`;
}

function fmtCurrency(value, currency = "USD") {
  if (value == null || Number.isNaN(value)) return "—";
  const symbol = CURRENCY_SYMBOL[currency] || "";
  return symbol + Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function fmtDate(iso) {
  if (!iso) return "";
  return iso.slice(0, 10);
}

function fmtUpdatedAt(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16) + " UTC";
}

function renderCompanyCard(company) {
  const a = document.createElement("a");
  a.className = "company-card";
  a.dataset.ticker = company.ticker;
  a.dataset.market = company.market || "";
  a.dataset.sector = company.sector || "";
  a.dataset.view = company.view || "";
  a.href = withBasePath(`/companies/${company.ticker}/`);
  a.innerHTML = `
    <div class="company-card__eyebrow">${company.market || "—"}・${company.ticker}</div>
    <h3 class="company-card__name">${company.name || ""}</h3>
    <div class="company-card__name-en">${company.name_en || ""}</div>
    <div class="company-card__price-row">
      <span class="company-card__price" data-card-price>——</span>
      <span class="company-card__price-meta" data-card-price-meta>加载中</span>
      <span class="company-card__target" data-card-target hidden></span>
    </div>
    <span class="company-card__satellite" aria-hidden="true">→</span>
  `;
  return a;
}

function applyFilters() {
  const grid = document.querySelector("[data-company-grid]");
  if (!grid) return;
  const cards = grid.querySelectorAll(".company-card");
  let visible = 0;
  cards.forEach((card) => {
    const ticker = (card.dataset.ticker || "").toLowerCase();
    const name = (card.querySelector(".company-card__name")?.textContent || "").toLowerCase();
    const nameEn = (card.querySelector(".company-card__name-en")?.textContent || "").toLowerCase();
    const matchQuery =
      !state.query ||
      ticker.includes(state.query) ||
      name.includes(state.query) ||
      nameEn.includes(state.query);
    const matchMarket = state.market === "all" || card.dataset.market === state.market;
    const matchSector = state.sector === "all" || card.dataset.sector === state.sector;
    const show = matchQuery && matchMarket && matchSector;
    card.style.display = show ? "" : "none";
    if (show) visible++;
  });
  const empty = grid.querySelector(".company-grid__empty");
  if (empty) empty.style.display = visible === 0 ? "" : "none";
}

function populateFilterOptions(companies) {
  const marketSelect = document.querySelector('[data-filter="market"]');
  const sectorSelect = document.querySelector('[data-filter="sector"]');
  if (marketSelect) {
    const markets = [...new Set(companies.map((c) => c.market).filter(Boolean))].sort();
    markets.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = MARKET_LABEL[m] || m;
      marketSelect.appendChild(opt);
    });
  }
  if (sectorSelect) {
    const sectors = [...new Set(companies.map((c) => c.sector).filter(Boolean))].sort();
    sectors.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      sectorSelect.appendChild(opt);
    });
  }
}

async function hydrateCardPrice(card) {
  const ticker = card.dataset.ticker;
  if (!ticker) return null;
  try {
    const res = await fetch(withBasePath(`/companies/${ticker}/data.json`), { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const snapshot = data.snapshot || {};
    const priceEl = card.querySelector("[data-card-price]");
    const metaEl = card.querySelector("[data-card-price-meta]");
    const targetEl = card.querySelector("[data-card-target]");
    if (priceEl) priceEl.textContent = fmtCurrency(snapshot.price, snapshot.currency);
    if (metaEl) {
      const parts = [];
      if (data.mock_data) parts.push("mock");
      if (data.updated_at) parts.push(fmtDate(data.updated_at));
      metaEl.textContent = parts.join(" · ") || "—";
    }
    if (targetEl) {
      // 有 mean 取 mean；否则 fallback median；都没有就隐藏
      const target = snapshot.analyst_target_mean ?? snapshot.analyst_target_median;
      if (target != null) {
        targetEl.innerHTML = `分析师目标价 <strong>${fmtCurrency(target, snapshot.currency)}</strong>`;
        targetEl.hidden = false;
      } else {
        targetEl.hidden = true;
      }
    }
    return data.updated_at;
  } catch (err) {
    console.warn("price fetch failed for", ticker, err);
    return null;
  }
}

function updateGlobalUpdatedAt(updates) {
  const valid = updates.filter(Boolean).sort();
  const target = document.querySelector("[data-global-updated]");
  if (!target) return;
  if (valid.length === 0) {
    target.textContent = "无数据";
    return;
  }
  target.textContent = fmtUpdatedAt(valid[valid.length - 1]);
}

function bindUI() {
  const search = document.querySelector('[data-filter="search"]');
  if (search) {
    search.addEventListener("input", (e) => {
      state.query = e.target.value.trim().toLowerCase();
      applyFilters();
    });
  }
  document.querySelectorAll("[data-filter]").forEach((el) => {
    if (el.matches("select")) {
      el.addEventListener("change", (e) => {
        const key = e.target.dataset.filter;
        state[key] = e.target.value;
        applyFilters();
      });
    }
  });
}

async function init() {
  const companies = Array.isArray(window.COMPANIES) ? window.COMPANIES : [];
  const grid = document.querySelector("[data-company-grid]");
  if (!grid) return;

  populateFilterOptions(companies);
  bindUI();

  if (companies.length === 0) {
    grid.innerHTML = `<div class="company-grid__empty">尚未收录任何公司报告。</div>`;
    return;
  }

  const cards = companies.map(renderCompanyCard);
  cards.forEach((card) => grid.appendChild(card));

  const empty = document.createElement("div");
  empty.className = "company-grid__empty";
  empty.style.display = "none";
  empty.textContent = "没有匹配的公司。";
  grid.appendChild(empty);

  const updates = await Promise.all(cards.map(hydrateCardPrice));
  updateGlobalUpdatedAt(updates);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
