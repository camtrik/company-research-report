#!/usr/bin/env python3
"""Generic 10-year PER/PBR calculator.

Supports US tickers (SEC EDGAR) and Japanese tickers (EDINET DB API).
Prices come from yfinance with split-basis alignment.

Usage:
    python per_pbr_10y.py --ticker 6098.T
    python per_pbr_10y.py --ticker AMZN --output result.json
    python per_pbr_10y.py --ticker 6098.T --years 5

Environment:
    EDINETDB_API_KEY  Required for Japanese tickers (free key from edinetdb.jp)

Output JSON:
{
  "per_pbr_10y": {
    "ticker": "6098.T",
    "years": [2025, 2024, ...],
    "per": [27.69, 29.97, ...],
    "pbr": [6.74, 5.16, ...],
    "year_end_price": [7430.0, 6680.0, ...],
    "eps": [268.32, 222.9, ...],
    "bps": [1102.86, 1295.4, ...]
  }
}
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf


SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "investment-research contact@example.com",
)
EDINET_DB_BASE_URL = "https://edinetdb.jp/v1"
JP_SUFFIXES = (".T", ".JP", ".OS", ".N", ".S", ".F", ".Q", ".P", ".BO")


def detect_market(ticker: str) -> str:
    upper = ticker.upper()
    for suffix in JP_SUFFIXES:
        if upper.endswith(suffix):
            return "JP"
    return "US"


def get_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 45) -> dict:
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def clean_float(value: Any) -> float:
    if value is None:
        return math.nan
    text = str(value).strip()
    if text in {"", "-", "nan", "None"}:
        return math.nan
    text = text.replace(",", "").replace("x", "").replace("%", "").replace("*", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if text in {"", "-", "."}:
        return math.nan
    return float(text)


def fetch_yfinance_prices(
    ticker: str, requested_dates: list[date]
) -> dict[date, dict]:
    if not requested_dates:
        return {}

    start = min(requested_dates) - timedelta(days=14)
    end = max(requested_dates) + timedelta(days=7)

    ticker_obj = yf.Ticker(ticker)
    history = ticker_obj.history(
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=False,
        actions=True,
    )
    if history.empty:
        raise RuntimeError(f"No yfinance price history for {ticker}")

    history = history.copy()
    if history.index.tz is not None:
        history.index = history.index.tz_localize(None)

    splits = ticker_obj.splits
    if len(splits) > 0 and splits.index.tz is not None:
        splits.index = splits.index.tz_localize(None)

    result: dict[date, dict] = {}
    for rd in requested_dates:
        eligible = history[history.index.date <= rd]
        if eligible.empty:
            continue
        selected_date = eligible.index[-1].date()
        split_adj_close = float(eligible.iloc[-1]["Close"])

        future_split_factor = 1.0
        for split_date, split_ratio in splits.items():
            if split_date.date() > selected_date:
                future_split_factor *= float(split_ratio)

        result[rd] = {
            "price_date": selected_date,
            "reporting_basis_close": split_adj_close * future_split_factor,
        }
    return result


# ── SEC EDGAR (US) ────────────────────────────────────────────────


def lookup_cik(ticker: str) -> str:
    url = "https://www.sec.gov/files/company_tickers.json"
    data = get_json(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=30)
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"CIK not found for US ticker: {ticker}")


def fetch_us_financials(ticker: str, start_year: int, end_year: int) -> list[dict]:
    cik = lookup_cik(ticker)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    cf = get_json(url, headers={"User-Agent": SEC_USER_AGENT})

    us_gaap = cf["facts"]["us-gaap"]
    eps_df = pd.DataFrame(us_gaap["EarningsPerShareDiluted"]["units"]["USD/shares"])
    equity_df = pd.DataFrame(us_gaap["StockholdersEquity"]["units"]["USD"])
    shares_df = pd.DataFrame(
        cf["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
    )

    rows: list[dict] = []
    for fy in range(start_year, end_year + 1):
        eps_cands = eps_df[
            (eps_df["form"] == "10-K")
            & (eps_df["fp"] == "FY")
            & (eps_df["fy"].astype(str) == str(fy))
            & (pd.to_datetime(eps_df["end"]).dt.year == fy)
        ].copy()
        if eps_cands.empty:
            continue

        fiscal_end = eps_cands["end"].mode().iloc[0]
        eps_cands = eps_cands[eps_cands["end"] == fiscal_end]

        if "start" in eps_cands.columns and not eps_cands.empty:
            fiscal_start = eps_cands["start"].mode().iloc[0]
            eps_cands = eps_cands[eps_cands["start"] == fiscal_start]

        if eps_cands.empty:
            continue
        eps_row = eps_cands.sort_values(["filed", "accn"]).iloc[-1]

        eq_sel = equity_df[
            (equity_df["form"] == "10-K")
            & (equity_df["fp"] == "FY")
            & (equity_df["fy"].astype(str) == str(fy))
            & (equity_df["end"] == fiscal_end)
        ]
        if eq_sel.empty:
            continue
        eq_row = eq_sel.sort_values(["filed", "accn"]).iloc[-1]

        sh_sel = shares_df[
            (shares_df["form"] == "10-K")
            & (shares_df["fp"] == "FY")
            & (shares_df["fy"].astype(str) == str(fy))
        ]
        if sh_sel.empty:
            continue
        sh_row = sh_sel.sort_values(["filed", "end"]).iloc[-1]

        eps_val = float(eps_row["val"])
        equity = float(eq_row["val"])
        shares = float(sh_row["val"])
        bps = equity / shares if shares else math.nan

        rows.append(
            {
                "fiscal_year": fy,
                "fiscal_end": fiscal_end,
                "eps": eps_val,
                "bps": bps,
            }
        )
    return rows


# ── EDINET DB (JP) ────────────────────────────────────────────────


def lookup_edinet_code(sec_code: str) -> str:
    url = f"{EDINET_DB_BASE_URL}/search?q={sec_code}"
    data = get_json(url, timeout=30)

    results = None
    for key in ("data", "results", "items"):
        if key in data:
            results = data[key]
            break
    if results is None:
        results = data if isinstance(data, list) else []
    if isinstance(results, dict):
        for inner_key in ("items", "companies"):
            if inner_key in results:
                results = results[inner_key]
                break
        if isinstance(results, dict):
            results = [results]
    if not isinstance(results, list):
        results = [results]

    for item in results:
        code = item.get("edinet_code") or item.get("edinetCode") or ""
        if code:
            return code

    raise ValueError(f"EDINET code not found for security code: {sec_code}")


def fetch_jp_financials(ticker: str, start_year: int, end_year: int) -> list[dict]:
    base_code = re.match(r"(\d+)", ticker).group(1)
    edinet_code = lookup_edinet_code(base_code)

    api_key = os.environ.get("EDINETDB_API_KEY")
    if not api_key:
        raise RuntimeError(
            "EDINETDB_API_KEY environment variable is required for Japanese tickers. "
            "Get a free key at https://edinetdb.jp"
        )

    headers = {"X-API-Key": api_key}
    financials = None

    for path in [
        f"companies/{edinet_code}/financials",
        f"company/{edinet_code}/financials",
    ]:
        url = f"{EDINET_DB_BASE_URL}/{path}"
        try:
            payload = get_json(url, headers=headers)
            data = payload.get("data", payload.get("financials", payload))
            if isinstance(data, list):
                financials = data
                break
        except Exception:
            continue

    if financials is None:
        raise RuntimeError(f"Could not fetch financials from EDINET DB for {ticker}")

    rows: list[dict] = []
    for item in financials:
        fy_raw = item.get("fiscal_year") or item.get("fiscalYear") or item.get("year")
        if fy_raw is None:
            continue
        fy = int(str(fy_raw).replace("FY", ""))
        if fy < start_year or fy > end_year:
            continue

        eps = clean_float(
            item.get("eps") or item.get("basic_eps") or item.get("basicEps")
        )
        bps = clean_float(
            item.get("bps") or item.get("book_value_per_share") or item.get("bookValuePerShare")
        )
        if math.isnan(eps) or math.isnan(bps):
            continue

        fiscal_end = (
            item.get("period_end") or item.get("periodEnd") or f"{fy}-03-31"
        )

        rows.append(
            {
                "fiscal_year": fy,
                "fiscal_end": fiscal_end,
                "eps": eps,
                "bps": bps,
            }
        )

    return sorted(rows, key=lambda r: r["fiscal_year"])


# ── Compute & Output ──────────────────────────────────────────────


def compute_per_pbr(ticker: str, financials: list[dict]) -> dict:
    dates = [
        datetime.strptime(f["fiscal_end"], "%Y-%m-%d").date() for f in financials
    ]
    prices = fetch_yfinance_prices(ticker, dates)

    years: list[int] = []
    per_list: list[float | None] = []
    pbr_list: list[float | None] = []
    price_list: list[float] = []
    eps_list: list[float] = []
    bps_list: list[float] = []

    for f, d in zip(financials, dates):
        if d not in prices:
            continue
        period_price = prices[d]["reporting_basis_close"]
        eps = f["eps"]
        bps = f["bps"]

        per_val = round(period_price / eps, 2) if eps != 0 else None
        pbr_val = round(period_price / bps, 2) if bps != 0 else None

        years.append(f["fiscal_year"])
        per_list.append(per_val)
        pbr_list.append(pbr_val)
        price_list.append(round(period_price, 2))
        eps_list.append(round(eps, 2))
        bps_list.append(round(bps, 2))

    years.reverse()
    per_list.reverse()
    pbr_list.reverse()
    price_list.reverse()
    eps_list.reverse()
    bps_list.reverse()

    return {
        "ticker": ticker,
        "years": years,
        "per": per_list,
        "pbr": pbr_list,
        "year_end_price": price_list,
        "eps": eps_list,
        "bps": bps_list,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute historical PER/PBR for any listed company"
    )
    parser.add_argument("--ticker", required=True, help="Ticker (e.g., 6098.T, AMZN)")
    parser.add_argument("--years", type=int, default=10, help="Number of years (default: 10)")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    end_year = datetime.now().year
    start_year = end_year - args.years + 1

    market = detect_market(args.ticker)
    print(f"Market: {market} | Ticker: {args.ticker} | Range: {start_year}-{end_year}", file=sys.stderr)

    if market == "JP":
        financials = fetch_jp_financials(args.ticker, start_year, end_year)
    else:
        financials = fetch_us_financials(args.ticker, start_year, end_year)

    if not financials:
        print("Error: no financial data found for the requested range.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(financials)} fiscal years of financial data", file=sys.stderr)

    result = compute_per_pbr(args.ticker, financials)
    output = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_pbr_10y": result,
    }

    json_str = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json_str + "\n", encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
