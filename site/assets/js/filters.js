/* ============================================================
   filters.js — Index page company grid + search + filter
   Data source: window.COMPANIES (injected by build.py from
   each company's <meta data-region="meta">).
   ============================================================ */

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

function fmtDate(iso) {
  if (!iso) return "";
  return iso.slice(0, 10);
}

function viewBadgeClass(view) {
  const v = (view || "").toLowerCase();
  if (v === "long") return "long";
  if (v === "watch") return "watch";
  if (v === "avoid" || v === "pass") return "avoid";
  return "neutral";
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
    <div class="company-card__footer">
      <span class="view-badge view-badge--${viewBadgeClass(company.view)}">${company.view || "—"}</span>
    </div>
    <span class="company-card__date">${company.last_updated ? "updated at " + fmtDate(company.last_updated) : ""}</span>
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

function updateGlobalUpdatedAt(companies) {
  const target = document.querySelector("[data-global-updated]");
  if (!target) return;
  const dates = companies.map((c) => c.last_updated).filter(Boolean).sort();
  target.textContent = dates.length ? dates[dates.length - 1] : "—";
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

function init() {
  const companies = Array.isArray(window.COMPANIES) ? window.COMPANIES : [];
  const grid = document.querySelector("[data-company-grid]");
  if (!grid) return;

  populateFilterOptions(companies);
  bindUI();

  if (companies.length === 0) {
    grid.innerHTML = `<div class="company-grid__empty">尚未收录任何公司报告。</div>`;
    return;
  }

  companies.sort((a, b) => (b.last_updated || "").localeCompare(a.last_updated || ""));
  const cards = companies.map(renderCompanyCard);
  cards.forEach((card) => grid.appendChild(card));

  const empty = document.createElement("div");
  empty.className = "company-grid__empty";
  empty.style.display = "none";
  empty.textContent = "没有匹配的公司。";
  grid.appendChild(empty);

  updateGlobalUpdatedAt(companies);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
