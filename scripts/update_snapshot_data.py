#!/usr/bin/env python3
"""
update_snapshot_data.py — Update the `snapshot` section of each company's
data.json with live market data from yfinance, EDINET DB (JP) and SEC EDGAR (US).

Usage:
    python scripts/update_snapshot_data.py --market JP
    python scripts/update_snapshot_data.py --market US
    python scripts/update_snapshot_data.py --market JP --ticker 6098

The script only writes data.json when the snapshot fields have materially
changed, avoiding unnecessary git churn. The `charts` section of data.json
is always preserved as-is.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
COMPANIES_DIR = SITE / "companies"

YF_SUFFIX: dict[str, str] = {
    "JP": ".T",
    "HK": ".HK",
    "US": "",
    "CN": ".SS",
}

CURRENCY_MAP: dict[str, str] = {
    "JP": "JPY",
    "US": "USD",
    "HK": "HKD",
    "CN": "CNY",
}

EDINET_DB_BASE = "https://edinetdb.jp/v1"
SEC_BASE = "https://data.sec.gov/api/xbrl/companyfacts"
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "investment-research contact@example.com"
)

META_TAG_RE = re.compile(r'<meta\s+data-region="meta"([^>]*?)>', re.DOTALL)
ATTR_RE = re.compile(r'data-([a-zA-Z\-]+)="([^"]*)"')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--market",
        required=True,
        choices=["US", "JP", "HK", "CN"],
        help="Market filter: only update companies with this data-market.",
    )
    parser.add_argument(
        "--ticker",
        help="Only update this specific ticker (must match data-ticker in HTML).",
    )
    return parser.parse_args()


# ── HTML scanning ──────────────────────────────────────────────────────────


def scan_companies(market: str) -> list[dict[str, str]]:
    if not COMPANIES_DIR.exists():
        return []
    rows: list[dict[str, str]] = []
    for company_dir in sorted(COMPANIES_DIR.iterdir()):
        if not company_dir.is_dir():
            continue
        index = company_dir / "index.html"
        if not index.exists():
            continue
        html = index.read_text(encoding="utf-8")
        m = META_TAG_RE.search(html)
        if not m:
            continue
        attrs = dict(ATTR_RE.findall(m.group(1)))
        if attrs.get("market") != market:
            continue
        rows.append(
            {
                "ticker": attrs.get("ticker", company_dir.name),
                "market": attrs["market"],
                "name": attrs.get("name", ""),
                "dir": str(company_dir),
            }
        )
    return rows


# ── Data helpers ───────────────────────────────────────────────────────────


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
        return None if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


def _get_info(ticker_yf: str) -> dict[str, Any]:
    t = yf.Ticker(ticker_yf)
    return t.info or {}


def _load_existing(data_path: Path) -> dict[str, Any] | None:
    if not data_path.exists():
        return None
    try:
        return json.loads(data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(data_path: Path, data: dict[str, Any]) -> None:
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ── TBV sources ────────────────────────────────────────────────────────────


def fetch_tbv_edinet(ticker: str) -> float | None:
    """Fetch TBV/share from EDINET DB API for Japanese companies.

    TBV = shareholders_equity - intangible_assets.
    Per-share uses shares_issued (not adjusting for treasury here —
    EDINET bps field already matches yfinance price basis).
    """
    api_key = os.environ.get("EDINETDB_API_KEY")
    if not api_key:
        return None

    edinet_code = _ticker_to_edinet_code(ticker)
    if not edinet_code:
        return None

    headers = {"X-API-Key": api_key}
    for path in (
        f"companies/{edinet_code}/financials",
        f"company/{edinet_code}/financials",
    ):
        try:
            r = requests.get(
                f"{EDINET_DB_BASE}/{path}", headers=headers, timeout=30
            )
            if r.status_code != 200:
                continue
            payload = r.json()
            items = payload.get("data", payload.get("financials", []))
            if not isinstance(items, list) or not items:
                continue

            items.sort(key=lambda x: x.get("fiscal_year", 0), reverse=True)
            latest = items[0]
            equity = _safe_float(latest.get("shareholders_equity"))
            intang = _safe_float(latest.get("intangible_assets"))
            shares = _safe_float(latest.get("shares_issued"))
            if equity is None or intang is None or not shares:
                continue

            tbv = equity - intang
            tbv_per_share = tbv / shares
            if tbv_per_share <= 0:
                return None
            return round(tbv_per_share, 4)
        except Exception:
            continue
    return None


def _ticker_to_edinet_code(ticker: str) -> str | None:
    mapping = {
        "6098": "E07801",
        "4568": "E04918",
        "3632": "E03939",
    }
    return mapping.get(ticker)


def fetch_tbv_sec(ticker: str) -> float | None:
    """Fetch TBV/share from SEC EDGAR companyfacts for US companies.

    TBV = StockholdersEquity - Goodwill - IntangibleAssetsNetExcludingGoodwill.
    Per-share uses DEI EntityCommonStockSharesOutstanding.
    """
    cik = _ticker_to_cik(ticker)
    if not cik:
        return None

    try:
        url = f"{SEC_BASE}/CIK{cik}.json"
        r = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None

    us_gaap = data.get("facts", {}).get("us-gaap", {})
    dei = data.get("facts", {}).get("dei", {})
    if not us_gaap or not dei:
        return None

    def _latest_annual(facts_list: list[dict]) -> dict | None:
        annual = [
            f
            for f in facts_list
            if f.get("form") == "10-K" and f.get("fp") == "FY"
        ]
        if not annual:
            annual = [f for f in facts_list if f.get("form") == "10-K"]
        if not annual:
            return None
        annual.sort(key=lambda x: (x["filed"], x.get("end", "")), reverse=True)
        return annual[0]

    required = {
        "StockholdersEquity": ("USD", us_gaap),
        "Goodwill": ("USD", us_gaap),
        "IntangibleAssetsNetExcludingGoodwill": ("USD", us_gaap),
        "EntityCommonStockSharesOutstanding": ("shares", dei),
    }
    values: dict[str, float] = {}
    for concept, (unit, taxonomy) in required.items():
        concept_data = taxonomy.get(concept, {})
        facts_list = concept_data.get("units", {}).get(unit, [])
        row = _latest_annual(facts_list)
        if row is None:
            return None
        values[concept] = float(row["val"])

    equity = values["StockholdersEquity"]
    goodwill = values["Goodwill"]
    intang = values["IntangibleAssetsNetExcludingGoodwill"]
    shares = values["EntityCommonStockSharesOutstanding"]

    tbv = equity - goodwill - intang
    if shares <= 0:
        return None
    tbv_ps = tbv / shares
    if tbv_ps <= 0:
        return None
    return round(tbv_ps, 4)


def _ticker_to_cik(ticker: str) -> str | None:
    mapping = {
        "NOW": "0001373715",
        "SOFI": "0001811864",
    }
    return mapping.get(ticker)


# ── Snapshot building ──────────────────────────────────────────────────────


def build_snapshot(
    ticker: str,
    market: str,
) -> dict[str, Any] | None:
    suffix = YF_SUFFIX.get(market, "")
    ticker_yf = ticker + suffix

    info = _get_info(ticker_yf)
    if not info:
        print(f"  [{ticker}] yfinance returned empty info for {ticker_yf}")
        return None

    price = _safe_float(info.get("currentPrice"))
    if price is None:
        print(f"  [{ticker}] no currentPrice in yfinance info")
        return None

    market_cap = _safe_float(info.get("marketCap"))
    ev = _safe_float(info.get("enterpriseValue"))
    total_debt = _safe_float(info.get("totalDebt"))
    total_cash = _safe_float(info.get("totalCash"))

    if ev is None and market_cap is not None:
        ev = market_cap + (total_debt or 0) - (total_cash or 0)

    mc_b = market_cap / 1e9 if market_cap is not None else None
    ev_b = ev / 1e9 if ev is not None else None

    pb = _safe_float(info.get("priceToBook"))

    revenue_growth = _safe_float(info.get("revenueGrowth"))
    operating_margin = _safe_float(info.get("operatingMargins"))
    net_margin = _safe_float(info.get("profitMargins"))

    ebitda = _safe_float(info.get("ebitda"))
    net_debt_to_ebitda = None
    if total_debt is not None and total_cash is not None and ebitda:
        net_debt = total_debt - total_cash
        net_debt_to_ebitda = round(net_debt / ebitda, 2)

    week52_low = _safe_float(info.get("fiftyTwoWeekLow"))
    week52_high = _safe_float(info.get("fiftyTwoWeekHigh"))
    analyst_target = _safe_float(info.get("targetMedianPrice"))

    is_jpy = market == "JP"

    def _fmt_price(val: float | None) -> float | None:
        if val is None:
            return None
        return round(val) if is_jpy and abs(val) >= 1000 else round(val, 2)

    def _fmt_large(val: float | None) -> float | None:
        if val is None:
            return None
        return round(val) if is_jpy else round(val, 2)

    snapshot: dict[str, Any] = {
        "price": _fmt_price(price),
        "currency": info.get("currency") or CURRENCY_MAP.get(market, "USD"),
        "market_cap_b": _fmt_large(mc_b),
        "ev_b": _fmt_large(ev_b),
        "pb": round(pb, 1) if pb is not None else None,
        "pb_tbv": None,
        "revenue_growth_ttm": round(revenue_growth, 4) if revenue_growth is not None else None,
        "operating_margin": round(operating_margin, 4) if operating_margin is not None else None,
        "net_margin": round(net_margin, 4) if net_margin is not None else None,
        "net_debt_to_ebitda": net_debt_to_ebitda,
        "week52_low": _fmt_price(week52_low),
        "week52_high": _fmt_price(week52_high),
        "analyst_target_median": _fmt_price(analyst_target),
    }

    if market == "JP":
        tbv_ps = fetch_tbv_edinet(ticker)
        if tbv_ps is not None:
            snapshot["pb_tbv"] = round(price / tbv_ps, 1)
    elif market == "US":
        tbv_ps = fetch_tbv_sec(ticker)
        if tbv_ps is not None:
            snapshot["pb_tbv"] = round(price / tbv_ps, 1)
    else:
        pass

    return snapshot


# ── Write logic ────────────────────────────────────────────────────────────


def _snapshot_changed(
    old_snap: dict[str, Any] | None,
    new_snap: dict[str, Any],
    skip_keys: set[str] | None = None,
) -> bool:
    if old_snap is None:
        return True
    skip = skip_keys or set()
    for key, new_val in new_snap.items():
        if key in skip:
            continue
        old_val = old_snap.get(key)
        if new_val is None and old_val is None:
            continue
        if new_val is None or old_val is None:
            return True
        if isinstance(new_val, float) and isinstance(old_val, float):
            if not math.isclose(new_val, old_val, rel_tol=1e-4, abs_tol=1e-2):
                return True
        elif new_val != old_val:
            return True
    return False


def update_company(company: dict[str, str]) -> bool:
    ticker = company["ticker"]
    market = company["market"]
    data_path = Path(company["dir"]) / "data.json"

    print(f"  [{ticker}] fetching snapshot ...", end=" ", flush=True)
    snapshot = build_snapshot(ticker, market)
    if snapshot is None:
        print("FAILED (no data)")
        return False
    print("OK")

    existing = _load_existing(data_path)
    old_snapshot = existing.get("snapshot") if existing else None

    MANUAL_FIELDS = {"pe_forward"}

    if old_snapshot:
        for key in MANUAL_FIELDS:
            if key in old_snapshot and old_snapshot[key] is not None:
                snapshot[key] = old_snapshot[key]

    if not _snapshot_changed(old_snapshot, snapshot, skip_keys=MANUAL_FIELDS):
        print(f"  [{ticker}] no material change, skipping write")
        return True

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data: dict[str, Any] = {
        "ticker": ticker,
        "updated_at": now,
        "snapshot": snapshot,
    }
    if existing and "charts" in existing:
        data["charts"] = existing["charts"]
    if existing and existing.get("mock_data"):
        pass

    _write_json(data_path, data)
    print(f"  [{ticker}] wrote data.json (updated_at={now})")
    return True


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    market = args.market

    companies = scan_companies(market)
    if args.ticker:
        companies = [c for c in companies if c["ticker"] == args.ticker]

    if not companies:
        print(f"[update_snapshot] no companies found for market={market}"
              + (f" ticker={args.ticker}" if args.ticker else ""))
        sys.exit(0)

    print(f"[update_snapshot] market={market} companies={len(companies)}")
    success = 0
    failed: list[str] = []

    for company in companies:
        try:
            if update_company(company):
                success += 1
            else:
                failed.append(company["ticker"])
        except Exception as exc:
            print(f"  [{company['ticker']}] EXCEPTION: {exc}")
            failed.append(company["ticker"])
        time.sleep(1)

    print(f"\n[update_snapshot] done: {success} ok, {len(failed)} failed")
    if failed:
        print(f"[update_snapshot] failed tickers: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
