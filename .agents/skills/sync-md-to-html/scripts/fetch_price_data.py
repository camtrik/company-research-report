#!/usr/bin/env python3
"""Fetch 10-year weekly price history for a single company.

Creates or updates site/companies/{TICKER}/data.json with price_10y chart data.
Run this once when adding a new company to the site. After that,
update_market_data.py handles ongoing weekly updates for all companies via CI.

Usage:
    python fetch_price_data.py --ticker 6098 --market JP
    python fetch_price_data.py --ticker AMZN
    python fetch_price_data.py --ticker 0700 --market HK

Output: site/companies/{TICKER}/data.json
{
  "ticker": "6098",
  "updated_at": "2026-05-17T00:00:00Z",
  "charts": {
    "price_10y": { "dates": ["2016-01-01", ...], "values": [1234.5, ...] }
  }
}
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

JP_SUFFIXES = (".T", ".JP", ".OS", ".N", ".S", ".F", ".Q", ".P", ".BO")
YF_SUFFIX: dict[str, str] = {"JP": ".T", "HK": ".HK", "US": "", "CN": ".SS"}


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "site" / "companies").exists():
            return parent
    return Path.cwd()


def detect_market(ticker: str) -> str:
    upper = ticker.upper()
    for suffix in JP_SUFFIXES:
        if upper.endswith(suffix):
            return "JP"
    return "US"


def yf_symbol(base_ticker: str, market: str) -> str:
    suffix = YF_SUFFIX.get(market.upper(), "")
    if suffix and not base_ticker.upper().endswith(suffix.upper()):
        return base_ticker + suffix
    return base_ticker


def fetch_weekly_prices(symbol: str) -> dict:
    ticker_obj = yf.Ticker(symbol)
    history = ticker_obj.history(period="10y", interval="1wk", auto_adjust=False)
    if history.empty:
        raise RuntimeError(f"No price history returned for {symbol}")
    df = history.copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    dates = [d.strftime("%Y-%m-%d") for d in df.index.date]
    values = [round(float(v), 2) for v in df["Close"]]
    return {"dates": dates, "values": values}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch initial 10-year weekly price data for a company"
    )
    parser.add_argument("--ticker", required=True, help="Base ticker (e.g. 6098, AMZN, 0700)")
    parser.add_argument(
        "--market", default=None, choices=["JP", "US", "HK", "CN"],
        help="Market code (auto-detected from ticker suffix if omitted)"
    )
    args = parser.parse_args()

    base_ticker = args.ticker
    market = args.market or detect_market(base_ticker)
    symbol = yf_symbol(base_ticker, market)

    # Use the numeric/base part as directory name (e.g. "6098.T" → "6098")
    dir_ticker = base_ticker.split(".")[0] if "." in base_ticker else base_ticker

    root = find_project_root()
    data_path = root / "site" / "companies" / dir_ticker / "data.json"

    print(f"Market: {market} | yfinance symbol: {symbol}", file=sys.stderr)
    print(f"Output: {data_path.relative_to(root)}", file=sys.stderr)

    print("Fetching 10-year weekly prices...", file=sys.stderr)
    price_data = fetch_weekly_prices(symbol)
    print(f"  {len(price_data['dates'])} weekly data points", file=sys.stderr)

    existing: dict = {}
    if data_path.exists():
        try:
            existing = json.loads(data_path.read_text(encoding="utf-8"))
            print("  Updating existing data.json", file=sys.stderr)
        except (json.JSONDecodeError, OSError):
            pass
    else:
        data_path.parent.mkdir(parents=True, exist_ok=True)
        print("  Creating new data.json", file=sys.stderr)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_data: dict = {
        "ticker": dir_ticker,
        "updated_at": now,
    }
    # Preserve any non-standard top-level fields from existing data
    for key, val in existing.items():
        if key not in ("ticker", "updated_at", "charts"):
            new_data[key] = val

    charts = {k: v for k, v in existing.get("charts", {}).items() if k != "price_10y"}
    charts["price_10y"] = price_data
    new_data["charts"] = charts

    data_path.write_text(
        json.dumps(new_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {data_path.relative_to(root)}", file=sys.stderr)


if __name__ == "__main__":
    main()
