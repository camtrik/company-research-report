# TSLA Historical PER / PBR

> Last updated: 2026-05-26. Source: SEC EDGAR companyfacts for financial facts, yfinance for period-end prices.

## Method

- Company: Tesla, Inc. (`TSLA`), SEC CIK `0001318605`.
- Period: fiscal years `2016-2025`, latest 10 completed fiscal years.
- Price: last trading close on or before fiscal year-end, using yfinance `Close`.
- Split basis: yfinance historical `Close` is split-adjusted. EPS and BPS are adjusted to the same current split basis using Tesla's `5-for-1` split on `2020-08-31` and `3-for-1` split on `2022-08-25`.
- PER: `price / diluted EPS`; years with negative EPS are shown as `N/M`.
- BPS: `stockholders' equity / split-adjusted shares outstanding`; PBR is `price / BPS`.

## Table

| FY | Fiscal end | Price date | Close | EPS | BPS | PER | PBR | Equity | Split-adjusted shares | Split factor after FY end | Filed | Accession |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 2016 | 2016-12-31 | 2016-12-30 | `$14.25` | `-0.31` | `1.96` | `N/M` | `7.3x` | `$4.8B` | `2,425M` | `15x` | 2019-02-19 | `0001564590-19-003165` |
| 2017 | 2017-12-31 | 2017-12-29 | `$20.76` | `-0.79` | `1.67` | `N/M` | `12.4x` | `$4.2B` | `2,534M` | `15x` | 2018-02-23 | `0001564590-18-002956` |
| 2018 | 2018-12-31 | 2018-12-31 | `$22.19` | `-0.38` | `1.90` | `N/M` | `11.7x` | `$4.9B` | `2,591M` | `15x` | 2019-02-19 | `0001564590-19-003165` |
| 2019 | 2019-12-31 | 2019-12-31 | `$27.89` | `-0.33` | `2.43` | `N/M` | `11.5x` | `$6.6B` | `2,720M` | `15x` | 2020-02-13 | `0001564590-20-004475` |
| 2020 | 2020-12-31 | 2020-12-31 | `$235.22` | `0.21` | `7.72` | `1,102.6x` | `30.5x` | `$22.2B` | `2,880M` | `3x` | 2021-02-08 | `0001564590-21-004599` |
| 2021 | 2021-12-31 | 2021-12-31 | `$352.26` | `1.63` | `9.74` | `215.7x` | `36.2x` | `$30.2B` | `3,101M` | `3x` | 2022-02-07 | `0000950170-22-000796` |
| 2022 | 2022-12-31 | 2022-12-30 | `$123.18` | `3.62` | `14.13` | `34.0x` | `8.7x` | `$44.7B` | `3,164M` | `1x` | 2023-01-31 | `0000950170-23-001409` |
| 2023 | 2023-12-31 | 2023-12-29 | `$248.48` | `4.30` | `19.67` | `57.8x` | `12.6x` | `$62.6B` | `3,185M` | `1x` | 2024-01-29 | `0001628280-24-002390` |
| 2024 | 2024-12-31 | 2024-12-31 | `$403.84` | `2.04` | `22.67` | `198.0x` | `17.8x` | `$72.9B` | `3,217M` | `1x` | 2025-01-30 | `0001628280-25-003063` |
| 2025 | 2025-12-31 | 2025-12-31 | `$449.72` | `1.08` | `21.89` | `416.4x` | `20.5x` | `$82.1B` | `3,752M` | `1x` | 2026-01-29 | `0001628280-26-003952` |

## Checks

- Row count: `10`.
- Fiscal years: `2016-2025`.
- PER/PBR recalculation from displayed raw columns was performed before rounding; max absolute error before display rounding was `0`.
- SEC source base URL: `https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json`.
- yfinance ticker: `TSLA`.
