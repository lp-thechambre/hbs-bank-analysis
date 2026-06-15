# Text Diff Signal Patterns

This document defines the text forensic signal types used in Layer 1 (Phase B) to detect disclosure changes, language drift, and selective disclosure patterns in Chinese bank annual and quarterly reports.

## Signal Type 1: DISCLOSURE_DISAPPEARANCE

### Definition

A previously disclosed metric, table, or section disappears from the current period's report without explanation.

### Detection Levels

| Level | Description | Example |
|-------|-------------|---------|
| Field | A single metric line item disappears | "对公客户数" was disclosed in 2024 annual report Section D but absent in 2025 |
| Table | An entire table is removed | Pillar 3 OV1 credit risk sub-categories table existed in T-1, replaced with aggregate only in T |
| Section | A whole disclosure section is dropped | "关联交易明细" section present in T-1, not present in T |

### Expected vs Suspicious

**Expected (not flagged)**:
- Regulatory change eliminates the requirement to disclose
- Business unit divested → related metrics naturally disappear
- Consolidation of multiple small items into one aggregate line

**Suspicious (flagged)**:
- Metric disappears while the underlying business still exists
- Peer banks continue to disclose the same metric
- The disappearance correlates with a negative trend in a related metric
- Metric was disclosed when favorable, disappeared when it turned unfavorable

### Cross-Validation

When a DISCLOSURE_DISAPPEARANCE is detected:
1. Check related quantitative metrics from Phase A.
2. If the related metric also shows deterioration → signal strength increases.
3. If the related metric is stable → possible explainable change (but still note it).

### Confidence

| Confidence | Criteria |
|-----------|----------|
| `high` | Field/table disappeared + related metric deteriorated + peers still disclose |
| `medium` | Field/table disappeared + related metric data unavailable |
| `low` | Field/table disappeared but related metric stable and peers also stopped disclosing |

---

## Signal Type 2: LANGUAGE_DRIFT

### Definition

The intensity, tone, or framing of risk-related language changes between reporting periods. Management's choice of words to describe the same risk evolves in a direction that warrants attention.

### Intensity Scale

| Level | Keywords (Chinese) | Keywords (English) |
|-------|-------------------|-------------------|
| 5 — Crisis | 严峻, 重大冲击, 系统性风险 | severe, systemic, crisis |
| 4 — Significant | 较大压力, 明显下降, 显著影响 | significant pressure, notable decline |
| 3 — Manageable | 可控, 一定压力, 有所放缓 | manageable, some pressure, moderation |
| 2 — Mild | 轻微, 基本稳定, 小幅波动 | mild, broadly stable, slight fluctuation |
| 1 — Benign | 良好, 稳健, 持续改善 | sound, robust, improving |

### Detection

Compare the same risk topic across periods:
- **T-1**: "房地产行业风险**较大**, 对公贷款质量面临**显著**压力"
- **T**: "房地产行业风险**可控**, 对公贷款质量**基本稳定**"

A 2+ level drop without a corresponding improvement in the quantitative metric is suspicious.

### Directional Assessment

| Direction | Description | Interpretation |
|-----------|-------------|----------------|
| MORE_CAUTIOUS | Language became more severe | Management is acknowledging problems — generally positive (transparency) |
| MORE_OPTIMISTIC | Language became less severe | May be genuine improvement OR glossing over problems |
| MORE_VAGUE | Specific terms replaced with generalities | Possible obfuscation |
| MORE_SPECIFIC | General terms replaced with specifics | Generally positive (increased transparency) |

### Cross-Validation

When LANGUAGE_DRIFT is detected:
1. Check the related quantitative metric trend.
2. Metric deteriorating + language becoming MORE_OPTIMISTIC → red flag (glossing over).
3. Metric deteriorating + language becoming MORE_CAUTIOUS → consistent (management is transparent).
4. Metric improving + language becoming MORE_OPTIMISTIC → consistent.

---

## Signal Type 3: ATTRIBUTION_SHIFT

### Definition

Changes in how management attributes performance outcomes — moving between internal attribution (own actions) and external attribution (macro environment).

### Attribution Categories

| Category | Description | Example |
|----------|-------------|---------|
| INTERNAL_POSITIVE | Credits own strategy/execution for good results | "得益于我行持续深化零售转型战略" |
| INTERNAL_NEGATIVE | Owns responsibility for bad results | "我行拨备计提不足, 需加强风险管理" |
| EXTERNAL_POSITIVE | Credits external factors for good results | "受益于宏观利率环境改善" (rare) |
| EXTERNAL_NEGATIVE | Blames external factors for bad results | "受宏观经济下行影响" |

### Detection

Compare attribution patterns across periods:

**Self-Serving Bias Pattern** (suspicious):
- Positive results attributed to INTERNAL factors
- Negative results attributed to EXTERNAL factors
- Pattern persists across multiple periods

**Ownership Pattern** (positive):
- Positive results: balanced internal/external attribution
- Negative results: includes INTERNAL_NEGATIVE acknowledgment

### Cross-Validation

When ATTRIBUTION_SHIFT is detected:
1. Check if the shift direction matches incentive structures (e.g., bonus targets, regulatory pressure).
2. Check L3 management_assessment for consistency with this finding.

---

## Signal Type 4: SELECTIVE_DISCLOSURE

### Definition

The bank highlights favorable metrics prominently while burying, omitting, or using non-standard definitions for unfavorable ones.

### Detection Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| HIGHLIGHT_FAVORABLE | Favorable metric in executive summary / opening paragraph | "我行零售AUM突破10万亿" as opening sentence |
| BURY_UNFAVORABLE | Unfavorable metric buried in footnote or appendix | NPL formation rate only in Note 35, not in risk management section |
| NON_STANDARD_DEFINITION | Uses non-standard metric definition that looks better | "Core NPL ratio" excluding certain loan categories |
| SELECTIVE_PEER_COMPARISON | Compares to peers only on favorable metrics | Compares NIM to peers but not NPL ratio |
| PERIOD_CHERRY_PICKING | Highlights favorable QoQ when YoY is unfavorable | "Q1 profit up 15% QoQ" when YoY is -5% |

### Detection Approach

1. Scan the executive summary / chairman's statement for prominently featured metrics.
2. Check if those metrics are the bank's STRONGEST metrics (cross-ref with peer_benchmark percentile).
3. Check if the bank's WEAKEST metrics (per peer_benchmark) are mentioned at all.
4. If weak metrics are mentioned, are they in a prominent location or buried?

### Cross-Validation

SELECTIVE_DISCLOSURE is inherently about emphasis. Cross-validate by:
- Checking if the highlighted metrics are genuinely strong vs peers.
- Checking where the weak metrics appear in the document structure.
- The section location in structured.md (Section C front vs Section D notes) is relevant evidence.

---

## Per-Section Comparison Guide

### MD&A — Business Overview (经营情况概述)

Compare across periods:
- Opening paragraph emphasis (what does management lead with?)
- Key performance metrics highlighted
- Tone and confidence level

### MD&A — Strategy Outlook (战略展望)

Compare across periods:
- Strategy vocabulary changes ("双轮驱动" → "聚焦零售" = significant shift)
- Investment priority changes
- Risk acknowledgment in outlook statements

### MD&A — Risk Management (风险管理)

Compare across periods:
- Risk categories listed and their ordering (priority changes)
- Specific risk metrics disclosed or omitted
- Mitigation language specificity

### Notes — Customer Data (客户数据)

Compare across periods:
- Customer segmentation detail (more granular or less?)
- Customer count disclosure (present or absent?)
- Segment breakdowns (does the bank still break out retail vs corporate?)

---

## Signal Recording Format

Each detected signal should be recorded in L1's `text_diff_signals` array:

```json
{
  "type": "DISCLOSURE_DISAPPEARANCE",
  "field": "corporate_customer_count",
  "severity": "medium",
  "evidence": "2024年报Section D明确披露对公客户数45,234户, 2025年报同章节在客户分层表中仅披露零售客户数, 对公客户数列删除",
  "cross_ref": "corporate_deposit_growth = -8.2% (P8), margin_deposit_contribution_bb = NOT_FOUND (缺失corporate_customer_count输入)"
}
```

Each signal must include `cross_ref` — the link between text pattern and quantitative data. This is the core value of the merged L1 design.
