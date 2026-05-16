---
name: historical-financial-data
description: Fetch and structure historical company financial data from primary/structured filing sources, then optionally combine it with yfinance prices to compute per-share metrics and valuation multiples. Use when Codex needs historical revenue, operating income, net income, EPS, BPS, equity, shares, cash flow, dividends, period-end prices, PER/P/E, PBR/P/B, or valuation multiple history for US stocks via SEC EDGAR API, Japanese stocks via EDINET DB API, and market prices via yfinance.
---

# Historical Financial Data

Build reproducible historical financial tables from filing-derived data. Use yfinance prices when the task needs market valuation metrics such as PER/PBR or period-end market cap.

Use the bundled reference script when the task matches the Amazon/Recruit pattern, or adapt its functions for other tickers:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pandas requests yfinance tabulate lxml beautifulsoup4 html5lib

# Required for EDINET DB financial endpoints. Never write this key into files.
export EDINETDB_API_KEY="..."

python .agents/skills/historical-financial-data/scripts/historical_per_pbr.py --output docs/historical-per-pbr.md
```

## Workflow

1. Identify the company identifiers:
   - US: ticker, SEC CIK, fiscal year-end.
   - Japan: ticker with Yahoo suffix such as `6098.T`, EDINET code such as `E07801`, fiscal year-end.
2. Fetch financial data:
   - US companies: use SEC EDGAR companyfacts.
   - Japanese companies: use EDINET DB API.
3. Normalize fiscal period, filing date, units, source URL, and source fields.
4. If the user asks for valuation ratios or market-based metrics, fetch yfinance daily price history around each fiscal period-end.
5. Pick the last trading close on or before the fiscal period-end.
6. Align split basis between price and per-share data.
7. Compute requested metrics, for example:
   - `PER = period_end_price / EPS`
   - `PBR = period_end_price / BPS`
   - `Market cap = period_end_price * shares`
   - `Net margin = net_income / revenue`
   - `ROE = net_income / average_equity`
8. Output a table with source fields: fiscal year, fiscal end, filing date, financial metrics, price fields if used, computed metrics, and financial source URL.

## SEC EDGAR

Use SEC EDGAR for US companies. Always send a descriptive `User-Agent`.

Endpoint:

```text
https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
```

Common facts:

| Need | Taxonomy / concept / unit |
|---|---|
| Revenue | `us-gaap:Revenues` or company-specific revenue concepts, `USD` |
| Operating income | `us-gaap:OperatingIncomeLoss`, `USD` |
| Net income | `us-gaap:NetIncomeLoss`, `USD` |
| Diluted EPS | `us-gaap:EarningsPerShareDiluted`, `USD/shares` |
| Basic EPS fallback | `us-gaap:EarningsPerShareBasic`, `USD/shares` |
| Equity | `us-gaap:StockholdersEquity`, `USD` |
| Shares for BPS | `dei:EntityCommonStockSharesOutstanding`, `shares` |
| Operating cash flow | `us-gaap:NetCashProvidedByUsedInOperatingActivities`, `USD` |
| Capital expenditure | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`, `USD` |

Selection rules:

- Prefer annual `10-K` facts with `fp == "FY"`.
- Match `fy`, `end`, and for flow/per-share facts also match annual `start`/`end` to avoid Q4-only facts.
- If multiple facts match, sort by `filed` and `accn`, then use the latest.
- Compute derived fields explicitly, such as `BPS = StockholdersEquity / EntityCommonStockSharesOutstanding`, unless a reliable company-provided field is available.
- Preserve `filed`, `accn`, `start`, `end`, and source URL for auditability.

## EDINET DB

Use EDINET DB for Japanese listed companies. Financial endpoints require `EDINETDB_API_KEY`; do not store the key in scripts, markdown, or git-tracked files.

Discovery:

```text
GET https://edinetdb.jp/v1/search?q=<company name or security code>
```

Use the returned `edinet_code` and `sec_code`. Example: Recruit Holdings is `E07801`, security code `60980`.

Financial endpoints to try:

```text
GET https://edinetdb.jp/v1/companies/{edinet_code}/financials
GET https://edinetdb.jp/v1/company/{edinet_code}/financials
```

Use header:

```text
X-API-Key: $EDINETDB_API_KEY
```

Extract annual fields equivalent to:

| Need | Typical field names |
|---|---|
| Fiscal year | `fiscal_year`, `fiscalYear`, `year` |
| Fiscal end | `period_end`, `periodEnd`; default Japanese March year-end to `YYYY-03-31` only after checking the company |
| Revenue | `revenue`, `net_sales`, `sales` |
| Operating income | `operating_income`, `operatingIncome` |
| Net income | `net_income`, `profit_attributable_to_owners_of_parent` |
| EPS | `eps`, `basic_eps`, `basicEps` |
| BPS | `bps`, `book_value_per_share`, `bookValuePerShare` |
| Equity | `equity`, `net_assets`, `total_equity` |
| Operating cash flow | `operating_cash_flow`, `operatingCashFlow` |
| Filing date | `submit_date`, `submitDate` |

If the API is unavailable and the user accepts a weaker source, use EDINET DB public pages only as a clearly labeled fallback. Do not mix fallback and API rows without a source column.

## yfinance Prices

Use yfinance when the requested output needs prices, market cap, or valuation multiples:

```python
import yfinance as yf

ticker = yf.Ticker("AMZN")
history = ticker.history(start="2020-12-15", end="2021-01-07", auto_adjust=False, actions=True)
splits = ticker.splits
```

Rules:

- Use the last trading `Close` on or before fiscal period-end.
- Strip timezone from yfinance indices before date comparisons.
- Keep `price_date` separately from `fiscal_end`.
- yfinance `Close` is split-adjusted. If EPS/BPS are as reported before a later split, multiply the historical `Close` by the cumulative split factor after `price_date` so price and per-share metrics share the same basis.
- Do not dividend-adjust the price for valuation multiples unless the user explicitly asks for total-return adjusted series.

## Calculations And Checks

Use raw numeric values for calculation and round only for presentation.

```python
per = period_end_price / eps
pbr = period_end_price / bps
market_cap = period_end_price * shares
net_margin = net_income / revenue
```

Validation checklist:

- Confirm row counts and fiscal years expected by the user.
- Recalculate derived metrics from the output columns; max absolute error should be zero except for display rounding.
- Flag negative or zero EPS as `N/M` if the user wants conventional valuation tables; otherwise leave the mathematical negative PER and note the reason.
- Check split events for the ticker and disclose any split-basis adjustment.
- Ensure no API keys or secrets appear in outputs, scripts, command logs, or committed files.
- Cite data source URLs or include source columns for SEC EDGAR, EDINET DB, and yfinance.

## Bundled Script

`scripts/historical_per_pbr.py` is a reference implementation that:

- Fetches Amazon annual EPS/equity/shares from SEC EDGAR companyfacts.
- Fetches Recruit EPS/BPS from EDINET DB API when `EDINETDB_API_KEY` is set.
- Falls back to EDINET DB public page parsing only when no API key is available.
- Fetches fiscal period-end prices from yfinance.
- Applies split-basis alignment and writes a Markdown table.

Read or patch this script when adapting the workflow to other companies or extending it from PER/PBR to broader historical financial metrics.
