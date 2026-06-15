# VOH Scoring Framework — Methodology Chapter 4

This document defines the VOH (Value-Optimal-Holdings) scoring methodology used in Layer 5 synthesis to produce composite scores and five-level ratings.

---

## VOH Formula

```
VOH = w1 × Dividend Score + w2 × Diversity Score + w3 × Growth Score
```

### Default Weights

| Weight | Value | Component | Rationale |
|--------|-------|-----------|-----------|
| w1 | 0.35 | Dividend Score | Dividends are the primary tangible return to shareholders in Chinese banking |
| w2 | 0.25 | Diversity Score | Portfolio diversification reduces risk; lower weight for single-bank mode |
| w3 | 0.40 | Growth Score | Quality-adjusted growth is the primary driver of long-term value |

Weights are configurable. Document any deviations from defaults in `analysis_trail.md`.

---

## Component 1: Dividend Score (0-100)

### Sub-Components

#### DPR Stability (40% of Dividend Score)

Measures the consistency of dividend payout ratio over time.

| CV of DPR (3yr) | Score Range | Description |
|-----------------|-------------|-------------|
| < 0.10 | 90-100 | Highly stable dividend policy |
| 0.10 - 0.20 | 70-89 | Reasonably stable, minor variations |
| 0.20 - 0.30 | 50-69 | Moderate variability |
| 0.30 - 0.50 | 30-49 | High variability — unpredictable dividend |
| > 0.50 | 0-29 | Erratic dividend policy or no clear policy |

**Edge case**: If only 2 years of DPR data → use CV of 2 data points with wider score bands (less confidence).

#### Dividend Resilience (35% of Dividend Score)

Measures dividend behavior during stress years (from L3 management assessment + L1 dividend data).

| Behavior | Score Range |
|----------|-------------|
| Cut dividend > 20% to preserve capital during stress | 90-100 |
| Cut dividend modestly (5-20%) | 80-89 |
| Maintained dividend while capital adequate | 70-79 |
| Maintained dividend despite capital pressure | 40-59 |
| Increased dividend moderately despite capital pressure | 20-39 |
| Increased dividend aggressively while capital weakened | 0-19 |

**Edge case**: Bank not listed / no dividend history during shock years → use 60 (neutral proxy). Document this.

#### Capital Erosion (CDP) (25% of Dividend Score)

Inverse mapping of CDP (Capital Dividend Penetration) to score.

| CDP Range | Score Range | Description |
|-----------|-------------|-------------|
| < 20% | 90-100 | Dividend well-covered by capital generation |
| 20-40% | 70-89 | Comfortable capital coverage |
| 40-60% | 50-69 | Moderate capital consumption |
| 60-80% | 30-49 | High capital consumption — dividend may be unsustainable |
| > 80% | 0-29 | Dividend consumes most of capital generation — likely unsustainable |

**Edge case**: CDP cannot be computed (missing CET1_net_before_dividend) → use DPR as partial proxy, score 50 for this sub-component.

### Dividend Score Calculation

```
Dividend Score = 0.40 × DPR_Stability + 0.35 × Dividend_Resilience + 0.25 × CDP_Inverse
```

---

## Component 2: Diversity Score (0-100)

### Multi-Bank Mode (2+ Banks)

The diversity score measures how much diversification benefit a bank adds to the portfolio.

**Method**:
1. Select key correlation metrics: ROE, NIM, NPL ratio, revenue growth, deposit growth.
2. For each bank, compute average pairwise correlation of these metrics with all other banks in the analysis set.
3. Lower average correlation = higher diversification benefit.

| Avg Pairwise Correlation | Score Range | Description |
|--------------------------|-------------|-------------|
| < 0.3 | 85-100 | High diversification benefit — low correlation with peers |
| 0.3 - 0.5 | 65-84 | Moderate diversification |
| 0.5 - 0.7 | 45-64 | Below-average diversification |
| > 0.7 | 25-44 | Low diversification — highly correlated with peers |

**Edge case**: Only 2 banks → pairwise correlation is a single data point. Score at midpoint of band.

### Single-Bank Mode

**Sector Diversity Proxy**: Fixed score of 60.

This acknowledges that diversity cannot be measured with one bank but a well-selected bank provides some implicit diversification. The score is slightly below average to avoid inflating single-bank VOH scores.

Document in output: "Diversity score uses sector proxy (60) in single-bank mode."

---

## Component 3: Growth Score (0-100)

### Sub-Components

#### Customer Quality Trend (40% of Growth Score)

Evaluates whether customer metrics are improving or deteriorating.

**Inputs**: Marginal deposit contribution (MDpst_bb, retail_MDpst), customer count trends, deposit growth composition.

| Signal | Score Impact |
|--------|-------------|
| Both corporate and retail marginal contribution positive + customer counts growing | +20 to +25 |
| One segment positive, one neutral | +10 to +19 |
| Both segments neutral/flat | 0 to +9 |
| One segment negative marginal contribution | -10 to -1 |
| Both segments negative OR customer disclosure stopped | -20 to -11 |

#### Marginal Profitability Trend (35% of Growth Score)

Evaluates whether the bank's incremental business is becoming more or less profitable.

**Inputs**: NIM trend, ROE trend, PPOP growth vs loan growth, fee income growth sustainability.

| Signal | Score Impact |
|--------|-------------|
| NIM stable/improving + PPOP growth > loan growth (positive operating leverage) | +20 to +25 |
| Mixed signals — NIM declining but fee income compensating | +10 to +19 |
| Broadly flat trends | 0 to +9 |
| NIM declining + PPOP growth < loan growth (negative operating leverage) | -10 to -1 |
| NIM declining rapidly + revenue declining | -20 to -11 |

#### Long-Termism Signals (25% of Growth Score)

Evaluates management's orientation toward long-term value creation.

**Inputs**: Integrity estimate (from L3 qual findings + L1 scan flags), resilience estimate (from L3 management assessment), L3 management_assessment.credibility.

| Resilience + Integrity + Credibility | Score Impact |
|--------------------------------------|-------------|
| Resilience ≥ 4 AND Integrity ≥ 85 AND credibility = "high" or "medium-high" | +15 to +20 |
| Resilience ≥ 2 AND Integrity ≥ 70 AND credibility not "low" | +8 to +14 |
| Mixed signals | 0 to +7 |
| Resilience < 0 OR Integrity < 60 OR credibility = "low" | -10 to -1 |
| Resilience ≤ -3 OR Integrity < 40 | -20 to -11 |

### Growth Score Calculation

```
Growth Score = 0.40 × Customer_Quality + 0.35 × Marginal_Profitability + 0.25 × Long_Termism
```

---

## Five-Level Rating

### Rating Criteria

| Rating | VOH Range | Integrity Floor | Resilience Floor | Description |
|--------|-----------|----------------|------------------|-------------|
| **STRONG_BUY** | ≥ 85 | ≥ 85 | ≥ 5 | Exceptional VOH + trustworthy management + proven resilience |
| **BUY** | 65-84 | ≥ 70 | ≥ 2 | Good VOH + acceptable integrity + demonstrated resilience |
| **HOLD** | 45-64 | No active red flags | — | Average VOH or moderate concerns preventing upgrade |
| **SELL** | 25-44 | OR < 60 | OR < 0 | Low VOH or integrity/resilience concerns |
| **STRONG_SELL** | < 25 | OR systemic issues | OR < -3 | Very low VOH or severe integrity/resilience failure |

### Rating Rules

1. **VOH is primary**: Start with VOH score range to determine initial rating tier.
2. **Integrity is a CAP, not a modifier**:
   - A bank with VOH = 95 but Integrity = 55 cannot be STRONG_BUY or BUY. Cap at HOLD.
   - A bank with VOH = 40 but Integrity = 95 stays SELL (integrity doesn't rescue poor fundamentals).
3. **Resilience is a TIEBREAKER**:
   - Two banks at BUY boundary (VOH = 64 vs 66): prefer higher resilience.
   - Resilience can push a borderline bank up or down one tier.
4. **STRONG_SELL requires evidence**: Cannot be assigned without documented red flags from L3 qual integrity_flags or L1 flags of systemic severity.

### Edge Cases

| Case | Handling |
|------|----------|
| Bank has DEGRADED L1 or L3 | Apply rating with available data, flag as "low confidence" |
| VOH at exact boundary (e.g., exactly 65) | Tier up (65 → BUY range, not HOLD range) |
| Integrity exactly at boundary | Round in bank's favor (e.g., 70 → meets BUY floor) |
| Single-bank mode | Normal rating process, diversity score uses proxy |
| Data gaps prevent VOH component calculation | Score remaining components, prorate; flag missing components |

---

## VOH Score Documentation

For each bank's final_output.json entry, document the component breakdown:

```json
{
  "code": "SH600036",
  "bank_name": "招商银行",
  "voh_score": 85.5,
  "dividend_score": 82.0,
  "diversity_score": 72.0,
  "growth_score": 92.0,
  "rating": "STRONG_BUY",
  "rank": 1,
  "integrity_score": 85,
  "resilience_score": 5
}
```
