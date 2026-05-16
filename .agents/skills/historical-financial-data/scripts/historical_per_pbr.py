#!/usr/bin/env python3
"""Build historical PER/PBR examples for Amazon and Recruit.

Primary data sources:
- Amazon: SEC EDGAR companyfacts API
- Recruit: EDINET DB API when EDINETDB_API_KEY is configured
- Prices: yfinance historical Close, adjusted back to the reporting split basis

The EDINET DB API requires a free key for company financial endpoints. To keep
this example runnable without credentials, Recruit falls back to the EDINET DB
public company page when the key is not present.
"""

from __future__ import annotations

import argparse
import math
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf


SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "investment-research-example contact@example.com",
)
EDINET_DB_BASE_URL = "https://edinetdb.jp/v1"
EDINET_DB_PUBLIC_PAGES = [
    "https://edinetdb.jp/company/E07801",
    "https://staging.edinetdb.jp/company/E07801",
]


@dataclass(frozen=True)
class PricePoint:
    requested_date: date
    price_date: date
    split_adjusted_close: float
    future_split_factor: float
    reporting_basis_close: float


def get_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = requests.get(url, headers=headers, timeout=45)
    response.raise_for_status()
    return response.json()


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


def fetch_yfinance_prices(ticker: str, requested_dates: list[date]) -> dict[date, PricePoint]:
    """Return the last trading close on or before each requested date.

    Yahoo/yfinance historical Close is adjusted for stock splits. SEC and EDINET
    per-share values are usually as reported at that time, so for years before a
    later split we multiply yfinance's Close by the cumulative future split
    factor. This puts price and EPS/BPS on the same share-count basis.
    """

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
        raise RuntimeError(f"No yfinance price history returned for {ticker}")

    history = history.copy()
    if history.index.tz is not None:
        history.index = history.index.tz_localize(None)

    splits = ticker_obj.splits
    if len(splits) > 0 and splits.index.tz is not None:
        splits.index = splits.index.tz_localize(None)

    result: dict[date, PricePoint] = {}
    for requested_date in requested_dates:
        eligible = history[history.index.date <= requested_date]
        if eligible.empty:
            continue

        selected_date = eligible.index[-1].date()
        split_adjusted_close = float(eligible.iloc[-1]["Close"])
        future_split_factor = 1.0
        for split_date, split_ratio in splits.items():
            if split_date.date() > selected_date:
                future_split_factor *= float(split_ratio)

        result[requested_date] = PricePoint(
            requested_date=requested_date,
            price_date=selected_date,
            split_adjusted_close=split_adjusted_close,
            future_split_factor=future_split_factor,
            reporting_basis_close=split_adjusted_close * future_split_factor,
        )
    return result


def fact_dataframe(companyfacts: dict[str, Any], taxonomy: str, concept: str, unit: str) -> pd.DataFrame:
    facts = companyfacts["facts"][taxonomy][concept]["units"][unit]
    return pd.DataFrame(facts)


def pick_sec_annual_fact(
    df: pd.DataFrame,
    *,
    fiscal_year: int,
    fiscal_end: str,
    fiscal_start: str | None = None,
) -> pd.Series | None:
    selected = df[
        (df["form"] == "10-K")
        & (df["fp"] == "FY")
        & (df["fy"].astype(str) == str(fiscal_year))
        & (df["end"] == fiscal_end)
    ].copy()

    if fiscal_start is not None and "start" in selected.columns:
        selected = selected[selected["start"] == fiscal_start]

    if selected.empty:
        return None

    selected = selected.sort_values(["filed", "accn"])
    return selected.iloc[-1]


def fetch_amazon_sec_rows(start_year: int = 2016, end_year: int | None = None) -> pd.DataFrame:
    if end_year is None:
        end_year = datetime.now().year - 1

    cik = "0001018724"
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    companyfacts = get_json(url, headers={"User-Agent": SEC_USER_AGENT})

    eps_df = fact_dataframe(companyfacts, "us-gaap", "EarningsPerShareDiluted", "USD/shares")
    equity_df = fact_dataframe(companyfacts, "us-gaap", "StockholdersEquity", "USD")
    shares_df = fact_dataframe(companyfacts, "dei", "EntityCommonStockSharesOutstanding", "shares")

    rows: list[dict[str, Any]] = []
    for fiscal_year in range(start_year, end_year + 1):
        fiscal_start = f"{fiscal_year}-01-01"
        fiscal_end = f"{fiscal_year}-12-31"
        eps_row = pick_sec_annual_fact(
            eps_df,
            fiscal_year=fiscal_year,
            fiscal_start=fiscal_start,
            fiscal_end=fiscal_end,
        )
        equity_row = pick_sec_annual_fact(
            equity_df,
            fiscal_year=fiscal_year,
            fiscal_end=fiscal_end,
        )
        shares_rows = shares_df[
            (shares_df["form"] == "10-K")
            & (shares_df["fp"] == "FY")
            & (shares_df["fy"].astype(str) == str(fiscal_year))
        ].copy()

        if eps_row is None or equity_row is None or shares_rows.empty:
            continue

        shares_row = shares_rows.sort_values(["filed", "end"]).iloc[-1]
        eps = float(eps_row["val"])
        equity = float(equity_row["val"])
        shares = float(shares_row["val"])
        bps = equity / shares if shares else math.nan

        rows.append(
            {
                "company": "Amazon.com, Inc.",
                "ticker": "AMZN",
                "market": "US",
                "fiscal_year": fiscal_year,
                "fiscal_end": fiscal_end,
                "eps": eps,
                "bps": bps,
                "equity": equity,
                "shares_for_bps": shares,
                "filing_date": eps_row["filed"],
                "financial_source": "SEC EDGAR companyfacts",
                "financial_source_url": url,
                "bps_note": "StockholdersEquity / DEI EntityCommonStockSharesOutstanding",
            }
        )

    return pd.DataFrame(rows)


def try_fetch_recruit_edinet_api(api_key: str) -> pd.DataFrame:
    headers = {"X-API-Key": api_key}
    errors: list[str] = []
    for path in ("companies/E07801/financials", "company/E07801/financials"):
        url = f"{EDINET_DB_BASE_URL}/{path}"
        try:
            payload = get_json(url, headers=headers)
        except Exception as exc:  # pragma: no cover - depends on external API
            errors.append(f"{path}: {exc}")
            continue

        data = payload.get("data", payload.get("financials", payload))
        if not isinstance(data, list):
            errors.append(f"{path}: unexpected payload shape")
            continue

        rows = []
        for item in data:
            fiscal_year_raw = item.get("fiscal_year", item.get("fiscalYear", item.get("year")))
            eps = clean_float(item.get("eps", item.get("basic_eps", item.get("basicEps"))))
            bps = clean_float(item.get("bps", item.get("book_value_per_share", item.get("bookValuePerShare"))))
            if fiscal_year_raw is None or math.isnan(eps) or math.isnan(bps):
                continue
            fiscal_year = int(str(fiscal_year_raw).replace("FY", ""))
            rows.append(
                {
                    "company": "Recruit Holdings Co., Ltd.",
                    "ticker": "6098.T",
                    "market": "JP",
                    "fiscal_year": fiscal_year,
                    "fiscal_end": item.get("period_end", item.get("periodEnd", f"{fiscal_year}-03-31")),
                    "eps": eps,
                    "bps": bps,
                    "filing_date": item.get("submit_date", item.get("submitDate")),
                    "financial_source": "EDINET DB API",
                    "financial_source_url": url,
                    "bps_note": "EDINET DB bps field",
                }
            )
        if rows:
            return pd.DataFrame(rows)

    raise RuntimeError("EDINET DB API did not return usable data: " + "; ".join(errors))


def fetch_recruit_public_fallback() -> pd.DataFrame:
    """Fallback for local runs without EDINETDB_API_KEY."""

    last_error: str | None = None
    for url in EDINET_DB_PUBLIC_PAGES:
        try:
            response = requests.get(url, timeout=45)
            tables = pd.read_html(StringIO(response.text))
        except Exception as exc:
            last_error = f"{url}: {exc}"
            continue

        for table in tables:
            columns = [str(column) for column in table.columns]
            if "EPS (円)" not in columns or "BPS (円)" not in columns:
                continue

            rows = []
            for _, item in table.iterrows():
                year_text = str(item["年度"]).strip()
                if "予" in year_text:
                    continue
                match = re.search(r"\d{4}", year_text)
                if not match:
                    continue
                fiscal_year = int(match.group())
                eps = clean_float(item["EPS (円)"])
                bps = clean_float(item["BPS (円)"])
                if math.isnan(eps) or math.isnan(bps):
                    continue
                rows.append(
                    {
                        "company": "Recruit Holdings Co., Ltd.",
                        "ticker": "6098.T",
                        "market": "JP",
                        "fiscal_year": fiscal_year,
                        "fiscal_end": f"{fiscal_year}-03-31",
                        "eps": eps,
                        "bps": bps,
                        "filing_date": None,
                        "financial_source": "EDINET DB public page fallback",
                        "financial_source_url": url,
                        "bps_note": "EDINET DB public investment metrics table",
                    }
                )
            if rows:
                return pd.DataFrame(rows)

    raise RuntimeError(f"Could not fetch Recruit fallback data. Last error: {last_error}")


def fetch_recruit_edinet_rows() -> pd.DataFrame:
    api_key = os.environ.get("EDINETDB_API_KEY")
    if api_key:
        return try_fetch_recruit_edinet_api(api_key)
    return fetch_recruit_public_fallback()


def attach_prices_and_ratios(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    dates = [datetime.strptime(value, "%Y-%m-%d").date() for value in df["fiscal_end"]]
    prices = fetch_yfinance_prices(ticker, dates)

    enriched = df.copy()
    enriched["_fiscal_end_date"] = dates
    enriched = enriched[enriched["_fiscal_end_date"].isin(prices)].copy()
    enriched_dates = list(enriched["_fiscal_end_date"])
    enriched["price_date"] = [prices[d].price_date.isoformat() for d in enriched_dates]
    enriched["yf_close_split_adjusted"] = [prices[d].split_adjusted_close for d in enriched_dates]
    enriched["future_split_factor"] = [prices[d].future_split_factor for d in enriched_dates]
    enriched["period_end_price"] = [prices[d].reporting_basis_close for d in enriched_dates]
    enriched["per"] = enriched["period_end_price"] / enriched["eps"]
    enriched["pbr"] = enriched["period_end_price"] / enriched["bps"]
    enriched = enriched.drop(columns=["_fiscal_end_date"])
    return enriched


def format_table(df: pd.DataFrame) -> str:
    table = df[
        [
            "fiscal_year",
            "fiscal_end",
            "price_date",
            "period_end_price",
            "eps",
            "bps",
            "per",
            "pbr",
            "filing_date",
            "financial_source",
        ]
    ].copy()
    table = table.sort_values("fiscal_year")
    for column in ["period_end_price", "eps", "bps", "per", "pbr"]:
        table[column] = table[column].map(lambda value: "" if pd.isna(value) else f"{value:,.2f}")
    table["filing_date"] = table["filing_date"].fillna("")
    return table.to_markdown(index=False)


def build_markdown(amzn: pd.DataFrame, recruit: pd.DataFrame, include_code: bool) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    script_path = Path(__file__).resolve()
    notes = []
    if (recruit["financial_source"] == "EDINET DB public page fallback").any():
        notes.append(
            "- 当前环境未配置 `EDINETDB_API_KEY`，Recruit 的 EPS/BPS 本次运行使用 EDINET DB 公开公司页 fallback；脚本已实现 EDINET DB API 优先路径，配置 key 后会走 API。"
        )
    else:
        notes.append("- Recruit 的 EPS/BPS 来自 EDINET DB API。")

    notes.append(
        "- yfinance 历史 `Close` 已按拆股调整；脚本用未来拆股因子把价格换回财报每股数据的报告口径。Amazon 2022 年 20:1 拆股前年度的 `period_end_price` 因此为当时交易口径价格。"
    )
    notes.append(
        "- Amazon BPS 不是 SEC 直接字段；脚本用 `StockholdersEquity / dei:EntityCommonStockSharesOutstanding` 推导。"
    )
    notes.append("- PER/PBR 均按 `period_end_price / EPS`、`period_end_price / BPS` 计算。")

    code_block = ""
    if include_code:
        code = script_path.read_text(encoding="utf-8")
        code_block = f"\n## 完整可复用代码\n\n代码文件：`{script_path}`\n\n```python\n{code}\n```\n"
    else:
        code_block = f"\n## 代码位置\n\n完整代码见 `{script_path}`。\n"

    return f"""# Amazon / Recruit 历史 PER 与 PBR 示例

生成时间：{generated_at}

## 口径说明

{chr(10).join(notes)}

## Amazon.com, Inc. (AMZN)

财务数据：SEC EDGAR companyfacts API  
股价数据：yfinance (`AMZN`)  
财年：12 月 31 日结束

{format_table(amzn)}

## Recruit Holdings Co., Ltd. (6098.T)

财务数据：EDINET DB  
股价数据：yfinance (`6098.T`)  
财年：3 月 31 日结束

{format_table(recruit)}

## 运行方法

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pandas requests yfinance tabulate lxml beautifulsoup4 html5lib

# Recruit 使用 EDINET DB API 时配置免费 key；不配置时脚本会尝试公开页 fallback。
export EDINETDB_API_KEY="YOUR_KEY"

python scripts/historical_per_pbr.py --output docs/historical-per-pbr-amzn-recruit.md
```

## 数据源

- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC Amazon companyfacts: https://data.sec.gov/api/xbrl/companyfacts/CIK0001018724.json
- EDINET DB API docs: https://edinetdb.jp/docs/api
- EDINET DB Recruit page: https://staging.edinetdb.jp/company/E07801
- yfinance: https://github.com/ranaroussi/yfinance
{code_block}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="docs/historical-per-pbr-amzn-recruit.md",
        help="Markdown output path.",
    )
    parser.add_argument(
        "--no-embed-code",
        action="store_true",
        help="Do not embed this script's full source in the Markdown.",
    )
    parser.add_argument("--amazon-start-year", type=int, default=2016)
    parser.add_argument("--amazon-end-year", type=int, default=2025)
    parser.add_argument("--recruit-start-year", type=int, default=2020)
    parser.add_argument("--recruit-end-year", type=int, default=2025)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    amzn = fetch_amazon_sec_rows(args.amazon_start_year, args.amazon_end_year)
    amzn = attach_prices_and_ratios(amzn, "AMZN")

    recruit = fetch_recruit_edinet_rows()
    recruit = recruit[
        (recruit["fiscal_year"] >= args.recruit_start_year)
        & (recruit["fiscal_year"] <= args.recruit_end_year)
    ].copy()
    recruit = attach_prices_and_ratios(recruit, "6098.T")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_markdown(amzn, recruit, include_code=not args.no_embed_code),
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
