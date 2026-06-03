# API Field → Screen Field Mapping

> Maps Eastmoney F10 API response columns to HBS-Screen internal fields.
> Primary endpoint: `https://datacenter.eastmoney.com/api/data/v1/get`

## Main Financial Data (RPT_F10_FINANCE_MAINFINADATA)

| Screen Field | API Column | Chinese Name | Availability | Notes |
|-------------|-----------|-------------|-------------|-------|
| `cet1` | `HXYJBCZL` | 核心一级资本充足率 | Partial | Q1 often null; take latest non-null value |
| `npl_ratio` | `NONPERLOAN` | 不良贷款率 | Full | Percentage value |
| `npl_balance` | `NON_PERFORMING_LOAN` | 不良贷款余额 | Full | Used for coverage ratio validation |
| `roe` | `ROEJQ` | ROE (季报年化) | Full | Annualized quarterly ROE |
| `pcr` | `BLDKBBL` | 拨备覆盖率 | Full | Percentage value |
| `total_assets` | `TOTAL_ASSETS_PK` | 总资产 | Full | In RMB (元) |
| `bps` | `BPS` | 每股净资产 | Full | Used for PB calculation |
| `eps` | `EPSJB` | 每股收益 | Full | Basic EPS |
| `net_profit` | `PARENTNETPROFIT` | 归母净利润 | Full | In RMB (元) |
| `gross_loans` | `GROSSLOANS` | 贷款总额 | Full | In RMB (元) |
| `loan_provision_ratio` | `LOAN_PROVISION_RATIO` | 贷款拨备率 | Full | Auxiliary for D2 |
| `cost_income_ratio` | `REVENUE_RATIO` | 成本收入比 | Partial | ~70% banks have values |
| `nim` | `NET_INTEREST_MARGIN` | 净息差 | Partial | ~60% banks; Q1 often missing |
| `car` | `NEWCAPITALADER` | 资本充足率 | Full | Auxiliary for D1 |
| `tier1_car` | `FIRST_ADEQUACY_RATIO` | 一级资本充足率 | Full | Auxiliary for D1 |

## Unavailable Fields (Do NOT fetch — always null or nonexistent)

| Field | Reason |
|-------|--------|
| `OVERDUE_LOANS` (逾期率) | API returns null for all banks |
| Write-off ratio (核销率) | No API field exists |
| Interest income ratio | Requires profit statement decomposition |
| Deposit cost rate (存款成本率) | No API field exists |

## Profit Statement Data (RPT_F10_PROFIT_STATEMENT)

Used for bank type classification (interest income ratio).

| Screen Field | API Column | Notes |
|-------------|-----------|-------|
| `net_interest_income` | `NET_INTEREST_INCOME` | Interest income net |
| `total_operating_income` | `TOTAL_OPERATE_INCOME` | Total operating revenue |
| `commission_income` | `COMMISSION_INCOME` | Fee/commission income (fallback) |

## Dividend Data (RPT_F10_DIVIDEND)

Used for DPR/DPS in D5 valuation scoring.

| Screen Field | API Column | Notes |
|-------------|-----------|-------|
| `dps` | `CASH_DIVIDEND_PER_SHARE` | Dividend per share |
| `dpr` | `DIVIDEND_RATIO` | Dividend payout ratio |

## Stock Price Data (Eastmoney Quote API)

Used for PB computation in D5.

| Screen Field | API Field | Notes |
|-------------|----------|-------|
| `close_price` | `f2` | Latest close price |
| `stock_code` | `f12` | Stock code |
| `stock_name` | `f14` | Stock name |

## N/A Handling Rules

1. Single field missing → mark as `null` in output, exclude from that sub-indicator's scoring.
2. All sub-indicators for a dimension missing → mark dimension score as `null`, exclude from composite.
3. >3 critical fields (cet1, npl_ratio, roe, pcr, bps) missing → bank excluded from Phase 2.
4. Never crash on missing data. Always produce partial results with `data_quality` annotations.

## Critical vs Non-Critical Fields

**Critical** (Phase 1 requires these):
- `cet1`, `npl_ratio`, `roe`, `pcr`, `bps`, `total_assets`, `eps`

**Non-critical** (enhance scoring but absence is tolerated):
- `nim`, `cost_income_ratio`, `loan_provision_ratio`, `car`, `tier1_car`, `dps`, `dpr`
