#!/usr/bin/env python3
"""Fetch weekly price data and annual PER/PBR for all companies.

Reads company metadata from site/companies/*/index.html <meta> tags.
Writes site/companies/{TICKER}/data.json for each company.

Usage:
    python scripts/update_market_data.py
    python scripts/update_market_data.py --ticker 6098
    python scripts/update_market_data.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
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

META_TAG_RE = re.compile(r'<meta\s+data-region="meta"([^>]*?)>', re.DOTALL)
ATTR_RE = re.compile(r'data-([a-zA-Z\-]+)="([^"]*)"')


def yf_symbol(ticker: str, market: str) -> str:
    suffix = YF_SUFFIX.get(market.upper(), "")
    if suffix and not ticker.endswith(suffix):
        return ticker + suffix
    return ticker


def scan_companies() -> list[dict]:
    companies: list[dict] = []
    if not COMPANIES_DIR.exists():
        return companies
    for d in sorted(COMPANIES_DIR.iterdir()):
        if not d.is_dir():
            continue
        index = d / "index.html"
        if not index.exists():
            continue
        text = index.read_text(encoding="utf-8")
        m = META_TAG_RE.search(text)
        if not m:
            continue
        attrs = dict(ATTR_RE.findall(m.group(1)))
        ticker = attrs.get("ticker", d.name)
        market = attrs.get("market", "US")
        companies.append({
            "ticker": ticker,
            "market": market,
            "dir": d,
            "symbol": yf_symbol(ticker, market),
        })
    return companies


def fetch_weekly_prices(ticker_obj: yf.Ticker) -> dict | None:
    history = ticker_obj.history(period="10y", interval="1wk", auto_adjust=False)
    if history.empty:
        return None
    df = history.copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    dates = [d.strftime("%Y-%m-%d") for d in df.index.date]
    values = [round(float(v), 2) for v in df["Close"]]
    return {"dates": dates, "values": values}


def fetch_per_pbr(
    ticker_obj: yf.Ticker,
    weekly_dates: list[str],
    weekly_values: list[float],
) -> dict | None:
    is_df = ticker_obj.income_stmt
    bs_df = ticker_obj.balance_sheet
    if is_df.empty or bs_df.empty:
        return None
    if "Diluted EPS" not in is_df.index:
        return None

    years: list[int] = []
    per_list: list[float | None] = []
    pbr_list: list[float | None] = []
    price_list: list[float] = []
    eps_list: list[float] = []
    bps_list: list[float] = []

    for col in is_df.columns:
        fiscal_end = col.date()
        year = col.year

        eps = is_df.loc["Diluted EPS", col]
        if eps is None or pd.isna(eps):
            continue

        equity = (
            bs_df.loc["Stockholders Equity", col]
            if "Stockholders Equity" in bs_df.index
            else None
        )
        shares = (
            bs_df.loc["Ordinary Shares Number", col]
            if "Ordinary Shares Number" in bs_df.index
            else None
        )
        if (
            equity is None
            or shares is None
            or pd.isna(equity)
            or pd.isna(shares)
            or float(shares) == 0
        ):
            continue

        bps = float(equity) / float(shares)
        fiscal_end_str = fiscal_end.strftime("%Y-%m-%d")

        best_idx = -1
        for i, d in enumerate(weekly_dates):
            if d <= fiscal_end_str:
                best_idx = i
            else:
                break
        if best_idx < 0:
            continue

        price = weekly_values[best_idx]
        eps_f = float(eps)
        per_val = round(price / eps_f, 2) if eps_f != 0 else None
        pbr_val = round(price / bps, 2) if bps != 0 else None

        years.append(year)
        eps_list.append(round(eps_f, 2))
        bps_list.append(round(bps, 2))
        price_list.append(round(price, 2))
        per_list.append(per_val)
        pbr_list.append(pbr_val)

    if not years:
        return None
    return {
        "years": years,
        "per": per_list,
        "pbr": pbr_list,
        "year_end_price": price_list,
        "eps": eps_list,
        "bps": bps_list,
    }


def update_company(company: dict, dry_run: bool = False) -> bool:
    symbol = company["symbol"]
    data_path = company["dir"] / "data.json"

    existing: dict = {}
    if data_path.exists():
        try:
            existing = json.loads(data_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    print(f"  Fetching weekly prices for {symbol}...")
    ticker_obj = yf.Ticker(symbol)
    price_data = fetch_weekly_prices(ticker_obj)
    if price_data is None:
        print(f"  ERROR: No price data for {symbol}")
        return False

    print(f"  Fetching PER/PBR for {symbol}...")
    per_pbr_data = fetch_per_pbr(ticker_obj, price_data["dates"], price_data["values"])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_data: dict = {
        "ticker": company["ticker"],
        "updated_at": now,
    }

    if "snapshot" in existing:
        new_data["snapshot"] = existing["snapshot"]

    new_data["charts"] = {"price_10y": price_data}
    if per_pbr_data is not None:
        new_data["charts"]["per_pbr_10y"] = per_pbr_data
    elif "charts" in existing and "per_pbr_10y" in existing.get("charts", {}):
        new_data["charts"]["per_pbr_10y"] = existing["charts"]["per_pbr_10y"]

    new_json = json.dumps(new_data, ensure_ascii=False, indent=2) + "\n"
    old_json = (
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n" if existing else ""
    )

    if new_json == old_json:
        print(f"  No changes for {company['ticker']}")
        return False

    if dry_run:
        print(f"  [dry-run] Would write {data_path.relative_to(ROOT)}")
    else:
        data_path.write_text(new_json, encoding="utf-8")
        print(f"  Updated {data_path.relative_to(ROOT)}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", help="Update only this ticker")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    companies = scan_companies()
    if args.ticker:
        companies = [c for c in companies if c["ticker"] == args.ticker]
        if not companies:
            print(f"Company {args.ticker} not found")
            sys.exit(1)

    print(f"Found {len(companies)} companies")

    success = 0
    failed: list[str] = []
    for company in companies:
        print(f"\nProcessing {company['ticker']} ({company['symbol']})...")
        try:
            changed = update_company(company, dry_run=args.dry_run)
            if changed or (company["dir"] / "data.json").exists():
                success += 1
            else:
                failed.append(company["ticker"])
        except Exception as exc:
            print(f"  ERROR: {exc}")
            failed.append(company["ticker"])

    print(f"\nDone: {success} ok, {len(failed)} failed")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
