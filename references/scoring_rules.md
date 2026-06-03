# Scoring Rules — HBS-Screen v1

> Detailed scoring methodology, thresholds, and formulas.
> All scoring is deterministic (no random elements). Same input → same output.
>
> **ARCHITECTURE-v1**: These rules are consumed by Layer 0 (data engineering,
> `generate_bank_cards.py`) to pre-compute scores into bank cards. AI spawns
> (Layer 1-3) access rules on-demand via `memory_search` rather than having
> them embedded in prompts.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-06 | Migrated from BRD-PLUS Phase 1/2/3 to ARCHITECTURE-v1 Layer 0-3 |
| v0.4 | 2026-05 | Initial scoring model per BRD-PLUS v0.4 |

---

## Layer 0: Data Engineering — Score Computation

All dimension scores are pre-computed by `generate_bank_cards.py` and embedded
into bank cards. Layer 1-3 spawns consume these scores from the cards, not by
re-computing them.

### Coarse Filtering Thresholds (used by Quant spawn, Layer 1)

Five rejection rules. First rule triggered = bank rejected (no further evaluation).

| Rule | Condition | Dimension | Rationale |
|------|-----------|-----------|-----------|
| R1 | CET1 < 8.5% | D1 | Regulatory floor (7.5% + 1% buffer) |
| R2 | NPL > 3.0% | D2 | Industry mean ~1.6% + 2σ |
| R3 | PCR < 120% | D2 | Regulatory minimum since 2020 |
| R4 | Net profit < 0 | D3 | Loss-making bank cannot be candidate |
| R5 | >3 critical fields missing | Data | Insufficient data for screening |

Critical fields: CET1 (HXYJBCZL), NPL (NONPERLOAN), ROE (ROEJQ), PCR (BLDKBBL), BPS, TOTAL_ASSETS_PK

---

## Bank Type Classification (Layer 0)

Determined by `generate_bank_cards.py` before scoring. Classification affects
D3 profitability sub-indicator weights.

### Primary Method: Interest Income Ratio
```
interest_income_ratio = NET_INTEREST_INCOME / TOTAL_OPERATE_INCOME

If ratio > 60%:   traditional_commercial
If 40% < ratio ≤ 60%: integrated
If ratio ≤ 40%:   trading_ib
```

### Fallback Method: Commission Income Ratio
```
fee_ratio = COMMISSION_INCOME / TOTAL_OPERATE_INCOME

If fee_ratio < 15%:  traditional_commercial
If fee_ratio < 35%:  integrated
Else:                trading_ib
```

### Type Overrides (last resort)
Pre-defined for well-known banks. See `bank_constants.py` `TYPE_OVERRIDES`.
Only applied when API profit statement data is unavailable.

---

## Five-Dimension Scoring (Layer 0 → embedded in cards)

All indicators scored 0-100 using **peer-group percentile within the same bank type**.

### Weight Matrix

| Dimension | Weight | Consumed by |
|-----------|--------|-------------|
| D1 Capital Preservation | 25% | Quant spawn, Synthesis spawn |
| D2 Asset Quality | 25% | Quant spawn, Synthesis spawn |
| D3 Profitability | 20% | Quant spawn, Synthesis spawn |
| D4 Growth | 15% | Quant spawn, Synthesis spawn |
| D5 Valuation | 15% | Quant spawn, Synthesis spawn |

### D1: Capital Preservation

| Sub-indicator | Weight | Scoring |
|--------------|--------|---------|
| CET1 ratio | 60% | Linear mapping: `100 * (val - min) / (max - min)` within peer group |
| Total CAR | 25% | Same linear percentile mapping |
| Tier 1 CAR | 15% | Same linear percentile mapping |

### D2: Asset Quality

| Sub-indicator | Weight | Scoring |
|--------------|--------|---------|
| NPL ratio (inverted) | 55% | Reverse linear mapping (lower NPL = higher score) |
| PCR | 30% | `min(100, PCR / 3.0)` — linear up to 300%, capped at 100 |
| Loan provision ratio | 15% | `min(100, ratio * 20)` — linear up to 5%, capped at 100 |

### D3: Profitability (Type-Dependent)

| Sub-indicator | Traditional | Integrated | Trading/IB |
|--------------|-------------|------------|------------|
| ROE | 40% | 35% | 30% |
| RORWA (estimated) | 30% | 25% | 20% |
| NIM | 20% | 15% | 0% |
| Non-interest income | 10% | 25% | 50% |

ROE and NIM: Linear percentile mapping within peer group.
RORWA: Estimated as `net_profit / (total_assets * 0.65)`. Placeholder scoring until API exposes direct RWA data.
Non-interest income: Fixed at 50 (neutral) when income decomposition unavailable.

### D4: Growth

Single-period mode: Scored as asset-size percentile (larger banks tend to have more moderate, sustainable growth).
Multi-period mode (future): Sigmoid mapping of YoY growth rates.

### D5: Valuation & Shareholder Return

| Sub-indicator | Weight | Scoring |
|--------------|--------|---------|
| PB relative value | 50% | Piecewise: PB ≤ 0.3 → 20, ≤ 0.5 → 50, ≤ 0.8 → 80, ≤ 1.0 → 90, ≤ 1.5 → 60, > 1.5 → 30 |
| DPR score | 30% | Piecewise: < 15% → 20, 15-30% → 60, 30-50% → 85, 50-60% → 70, > 60% → 20 |
| EPS yield | 20% | Piecewise: ≥ 10% → 90, ≥ 6% → 75, ≥ 4% → 50, ≥ 2% → 30, < 2% → 10 |

### Composite Score
```
Score = D1 × 0.25 + D2 × 0.25 + D3 × 0.20 + D4 × 0.15 + D5 × 0.15
```
Missing dimensions are excluded; remaining weights re-normalized.

---

## Curiosity Flags (Layer 0 pre-computed, Layer 1 reinforced)

Flags are pre-computed by `generate_bank_cards.py` and written into bank cards.
The Quant spawn (Layer 1) independently re-evaluates these during its scan and
may add or adjust flags based on its pattern recognition analysis.

| ID | Name | Level | Trigger |
|----|------|-------|---------|
| F1 | CET1 Margin Squeeze | WATCH | CET1 < 9.5% |
| F2 | NPL Outlier | REJECT | NPL > peer_mean + 2σ |
| F3 | Provisioning Inadequacy | WATCH | 120% ≤ PCR < 160% |
| F4 | NIM Critical | WATCH | NIM < 1.0% (single-period proxy) |
| F5 | Leverage-Inflated ROE | WATCH | ROE > p75 AND ROA < 0.3% |
| F6 | Unsustainable DPR | WATCH | DPR > 60% |
| F7 | DPS Decline | — | Reserved (requires multi-period data) |
| F8 | Cost-Income Elevated | INFO | Cost-income ratio > 60% |
| F9 | Profitability Concern | INFO | ROE < 5% |
| F10 | Thin Capital Buffer | WATCH | CAR < 12% |
| F11 | Data Quality Poor | INFO | >1 critical field missing |
| F-NCO | Write-off Ratio | — | Reserved (API data unavailable) |

---

## Layer 3: Synthesis — Conflict Resolution & Candidate Selection

The Synthesis spawn (Layer 3) does NOT re-score banks. It classifies banks
into three consensus groups and resolves only conflicts:

| Consensus Group | Criteria | Action |
|----------------|----------|--------|
| HIGH_CONFIDENCE_PASS | Quant PASS + Qual PASS, no REJECT-level edge anomaly | Auto-include, no review |
| UNANIMOUS_REJECT | Quant REJECT + Qual REJECT | Auto-exclude, no review |
| CONFLICT | Mixed signals between layers | Judge resolves by conflict pattern |

### Conflict Patterns (resolved in batch)

- **Pattern A**: Quant WATCH + Qual PASS → trust qual if reasoning is specific
- **Pattern B**: Quant PASS + Qual WATCH/REJECT → trust qual (more context, peer comparison)
- **Pattern C**: Edge anomaly + both PASS → check anomaly severity; high severity triggers 1 card read
- **Pattern D**: Quant REJECT + Qual PASS → read card; hard thresholds stand unless exceptional

### Target & Fallback

- Target: 10-15 candidates
- If >15: prioritize by qual group_rank, data quality, unresolved edge count
- If <10: relax criteria, include borderline banks marked "included to meet minimum"

---

## Determinism Guarantee

1. All formulas are closed-form mathematical functions (no random, no sampling).
2. Peer-group statistics are deterministic: sorted data → percentile via linear interpolation.
3. Curiosity Flags are threshold-based comparisons against computed peer stats.
4. Layer 1 (Quant) analysis is AI-driven and may vary between runs (this is
   intentional — the Synthesis layer reconciles variability).
5. Layer 0 score computation is fully deterministic. Same raw data → same scores.
