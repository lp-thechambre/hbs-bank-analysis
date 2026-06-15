# VOH Framework — Portfolio Cross-Evaluation

> VOH = Value-Optimal-Holdings. The composite score from Depth that ranks banks by quality.
> In Portfolio, VOH is the **direction** signal: "who is better." Market cap is the starting point.

## VOH Sub-Dimensions

Depth produces three sub-scores (0-100 each):

| Dimension | Weight | What it measures | Portfolio relevance |
|-----------|--------|-----------------|-------------------|
| Dividend Score | 33.3% | Capital return discipline, CDP ratio, dividend stability, payout history under stress | Critical for dividend-oriented tactical versions |
| Diversity Score | 33.3% | Business diversification, regional spread, revenue mix, sector exposure concentration | Key for identifying hidden common-risk factors |
| Growth Score | 33.3% | Earnings growth trajectory, efficiency trends, strategic expansion quality | Can inflate VOH if management is aggressive but undisciplined |

## VOH(Depth) → VOH(Portfolio) Adjustment

The Portfolio skill does NOT re-score VOH. It adjusts the **ranking order** based on cross-evaluation findings:

```
VOH(Depth) ranking → Curiosity Checklist cross-eval → VOH(Portfolio) ranking
```

### Adjustment Rules

1. **Ranking only, not scores**: Move banks up or down in rank. Do not change the VOH number.
2. **Reasons required**: Every rank adjustment must cite specific checklist findings.
3. **Consensus strength**: Multiple checklist items agreeing → larger rank adjustment (up to ±3 positions).
4. **Conflicting signals**: Mixed evidence → smaller adjustment (±1), note uncertainty.
5. **Rating as floor/ceiling**:
   - STRONG_SELL: excluded from ranking entirely
   - SELL: pushed to bottom of ranking
   - STRONG_BUY: cannot be pushed below top-half

### Adjustment Magnitude Guide

| Signal Strength | Max Rank Change | Example |
|----------------|----------------|---------|
| Strong consensus (3+ items agree) | ±3 | Quad II + NPL rank #1 + Efficiency improving |
| Moderate consensus (2 items agree) | ±2 | Quad I + Capital buffer top 3 |
| Single signal | ±1 | Dividend discipline only |
| Conflicting signals | ±1 with note | Quad I but Integrity < 75 |

## Strategy Version → VOH Sub-Dimension Preference

Different tactical versions emphasize different VOH sub-dimensions:

| Tactical Version | Primary VOH Dimension | Secondary | Disregard |
|-----------------|----------------------|-----------|-----------|
| Low Beta Defensive | Diversity (stability) | Dividend | Growth |
| High Beta Aggressive | Growth (momentum) | Diversity | (none) |
| Dividend Oriented | Dividend (payout) | Diversity | Growth |
| Balanced / Equal | All equally | — | — |

## Integrity & Resilience in VOH

Integrity and resilience are NOT part of the VOH composite score, but they interact:

- **High VOH + Low Integrity**: Red flag — VOH may be inflated by aggressive growth. Check if growth_score is the primary driver.
- **Low VOH + High Integrity**: Potential undervaluation — management quality not reflected in current VOH.
- **Resilience as tiebreaker**: When two banks have similar VOH and similar market cap, resilience score breaks the ranking tie.

## Checklist Items That Affect VOH Ranking

| Checklist Item | Affects | Adjustment Logic |
|---------------|---------|-----------------|
| 2.1 VOH x MC 2x2 | Initial sort | Quad II → rank up; Quad IV → rank down |
| 2.2 VOH x Resilience | Cross-check | High VOH / Low Resilience → cap rank gain |
| 2.3 NPL Strictness | Cross-check | Loose recognition → penalize rank |
| 2.7 Marginal Efficiency | Cross-check | Declining efficiency → penalize rank |
| 2.8 Integrity | Cross-check | Low integrity → cap rank or penalize |
| 2.10 Industry Foresight | Gold/mining | First mover → rank up; Laggard → rank down |
