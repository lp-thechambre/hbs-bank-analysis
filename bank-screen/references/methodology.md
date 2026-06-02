# Methodology References — HBS-Screen v0.4

> Points to relevant HBS (Hermes Banking Stock) methodology chapters.
> For use with downstream Depth, Voh, and Reperio skills.

## HBS v0.3 Framework

The HBS-Screen Skill implements the **first-layer funnel** of the HBS research framework:

| Layer | Skill | Purpose |
|-------|-------|---------|
| 1. Screen | `bank-screen` (this skill) | 42 → 10-15 candidates |
| 2. Depth | `bank-depth` (future) | Deep fundamental analysis |
| 3. Voh | `bank-voh` (future) | Valuation + optionality + hedge |
| 4. Reperio | `bank-reperio` (future) | Portfolio construction |

## Key Methodological Decisions

### 1. Peer-Group Relative Scoring (not Absolute)
Chinese banking sector trades at structurally low PB multiples. Absolute thresholds (PB > 1.5, PB < 0.5) are meaningless when 90% of the sector is below 1.0x. All thresholds are relative to bank type peers.

Reference: HBS v0.3, Chapter 4 "Valuation Framework for Chinese Banks"

### 2. Bank Type Classification
The traditional/joint-stock/city/rural classification used by CSRC is not sufficient for financial analysis. HBS classifies by business model (interest income dependency), which determines which metrics are informative.

Reference: HBS v0.3, Chapter 2 "Bank Typology"

### 3. RORWA as ROE Complement
ROE = ROA × Leverage. A bank with 8% CET1 can show higher ROE than one with 14% CET1 even if its underlying asset profitability is worse. RORWA (net profit / risk-weighted assets) strips out the leverage effect.

Reference: HBS v0.3, Chapter 5 "Profitability Decomposition"

### 4. Single-Year DPR Only
BRD-PLUS constrains Screen to single-year dividend analysis. Multi-year dividend resilience (shock-year behavior) and dividend sustainability modeling are Depth-stage work.

Reference: HBS v0.3, Chapter 7 "Shareholder Return Analysis"

### 5. Real Estate Exposure Deferred
Real estate sector exposure analysis requires: (a) industry-segment loan decomposition, (b) disclosure standardization across banks, (c) developer-specific risk assessment. None of this is standardized or API-accessible for Screen.

Reference: HBS v0.3, Chapter 6 "Sector Concentration Risk"

### 6. NCO Write-off Rate (Reserved)
The write-off ratio (nuclear provision consumption / beginning NPL balance) is the best leading indicator of hidden NPL accumulation, but Eastmoney F10 API does not expose the required fields. Flag F-NCO is reserved in the scoring model for future activation.

Reference: HBS v0.3, Chapter 3 "Asset Quality: Beyond NPL Ratio"

## Data Source Acknowledgments

- **Eastmoney F10 API**: Primary financial data source. Rate-limited, no authentication required for public endpoints.
- **Eastmoney Quote API**: Real-time stock prices for PB/EPS yield computation.
- **AKShare** (fallback): Open-source Chinese financial data interface.

## API Fair Use

- Respect rate limits: minimum 2-second gap between different report-type API calls.
- Include User-Agent and Referer headers.
- No authentication bypass or scraping of restricted endpoints.
- This skill is for research/educational purposes. Not for commercial redistribution of Eastmoney data.
