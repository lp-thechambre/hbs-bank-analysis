# Scenario Reasoning Framework

> Portfolio uses AI-driven scenario reasoning instead of historical backtesting or Monte Carlo simulation.
> The AI reasons from bank narratives + macro knowledge to assess "what happens if."

## Why Not Backtesting / Monte Carlo

1. **Backtesting is circular**: Using historical portfolio performance to validate current judgments assumes the past is a reliable guide. In Chinese banking, structural shifts (LPR reform, real estate deleveraging, regulatory tightening) make history less predictive.
2. **Monte Carlo over-engineering**: The methodology has 23 chapters of judgment frameworks, scorecards, and red-flag detectors — not a single chapter requiring Monte Carlo simulation.
3. **Narrative contains forward-looking signal**: Bank management's own scenario disclosures, stress test results (per Pillar 3), and strategic pivots are forward-looking data that AI can synthesize.

## Scenario Framework

### Scenario 1: Rate +/- 100bp

**Question**: How does the portfolio behave under a parallel rate shift?

**AI reasoning inputs**:
- Liability structure (retail/corporate/interbank) from narratives
- Asset duration hints from depth analysis
- NIM sensitivity annotations (if Depth provided them)
- Historical NIM behavior under rate cycles (AI general knowledge)

**Output**: Ranking from most vulnerable to most resilient, with aggregate vulnerable weight.

### Scenario 2: Credit Shock (+200bp NPL)

**Question**: If systemic NPL jumps 200bp, which banks have the thin provision buffers?

**AI reasoning inputs**:
- Provision coverage ratios from depth
- NPL / overdue ratios
- Loan loss reserve adequacy
- Sector concentration (which sectors would drive the shock)

**Output**: Thin-buffer bank list with aggregate weight, duration estimate.

### Scenario 3: Real Estate Continued Decline

**Question**: What if real estate collateral values fall another 15-20%?

**AI reasoning inputs**:
- Real estate exposure percentages
- LTV ratios on real estate collateral
- Developer loan concentrations
- Related sector exposures (construction, building materials)

**Output**: Banks grouped by exposure severity, aggregate affected weight.

### Scenario 4: Regulatory Capital Tightening

**Question**: What if CBRC raises systemic bank CET1 requirements by 100bp?

**AI reasoning inputs**:
- Current CET1 buffers above regulatory minimums
- Internal capital generation rates (from depth efficiency analysis)
- Dividend payout commitments (CDP ratios)

**Output**: Banks that would need to cut dividends or raise capital, aggregate weight.

### Scenario 5: LPR Compression (NIM Squeeze)

**Question**: What if LPR is cut by an additional 25bp with deposit rates sticky?

**AI reasoning inputs**:
- Loan yield sensitivity (retail vs corporate loan mix)
- Deposit cost stickiness (retail time deposit proportion)
- Off-balance-sheet income proportion (less rate-sensitive revenue)

**Output**: NIM-compression sensitivity ranking.

## Scenario Integration into Report

Each scenario produces:
1. **Ranking**: Banks ordered by vulnerability
2. **Aggregate weight**: Total portfolio weight of the most vulnerable banks
3. **Threshold check**: Is the aggregate vulnerable weight acceptable given the investment objective?
4. **Mitigation suggestion**: If weight is concerning, which bank(s) to reduce?

The scenario findings feed directly into the report's "Risk Warnings" section.

## AI Reasoning Guidelines

When executing scenario analysis:
- **Use narrative evidence**: Quote specific disclosures about asset duration, deposit structure, sector exposure
- **Acknowledge uncertainty**: Mark confidence (high/medium/low) for each scenario assessment
- **No false precision**: "Bank A is likely more vulnerable than Bank B" is sufficient — no need for estimated basis-point impacts
- **Cross-reference with checklist**: Scenario findings should be consistent with Phase 2 checklist findings (e.g., rate sensitivity clustering)
