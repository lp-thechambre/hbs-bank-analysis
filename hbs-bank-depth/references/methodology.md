# HBS Methodology Reference

## Upstream Document

**Document**: RBM-BNK-2026-003: A-Share Banking Investment Research Methodology v0.3

The HBS methodology document defines the complete analytical framework for A-share bank evaluation. This skill implements the depth analysis subset of that methodology.

## Chapter Mapping

| Methodology Chapter | Depth Skill Implementation |
|---------------------|---------------------------|
| Ch1: Introduction & Scope | SKILL.md (Overview, Design Principles) |
| Ch2: Pipeline Architecture | SKILL.md (Pipeline Architecture, Layer Responsibilities) |
| Ch3: Capital Adequacy | formula_graph.json (capital formulas), question_compass.md (Ch3) |
| Ch4: VOH Framework | voh_framework.md (complete scoring methodology) |
| Ch5: Asset Quality | formula_graph.json (NPL/provision formulas), question_compass.md (Ch5) |
| Ch6: Profitability & Efficiency | formula_graph.json (ROE/ROA/PPOP formulas), question_compass.md (Ch6) |
| Ch7: Liquidity | formula_graph.json (LCR/NSFR/LDR), question_compass.md (Ch7) |
| Ch8: Customer Base | formula_graph.json (MDpst_bb, retail_MDpst), question_compass.md (Ch8) |
| Ch9: Net Interest Margin | formula_graph.json (NIM decomposition), question_compass.md (Ch9) |
| Ch10: Fee Income | formula_graph.json (fee_income_ratio), question_compass.md (Ch10) |
| Ch11: Operating Efficiency | formula_graph.json (cost_income, revenue_per_employee), question_compass.md (Ch11) |
| Ch12: Growth | formula_graph.json (growth rates), question_compass.md (Ch12) |
| Ch13: Risk Appetite | question_compass.md (Ch13) |
| Ch14: Credit Risk | question_compass.md (Ch14) |
| Ch15: Market Risk | question_compass.md (Ch15) |
| Ch16: Operational Risk | question_compass.md (Ch16) |
| Ch17: Capital Planning | question_compass.md (Ch17) |
| Ch18: Concentration Risk | formula_graph.json (HHI, corporate_loan_ratio), question_compass.md (Ch18) |
| Ch19: Resilience | voh_framework.md — scores assessed per-bank by Vice (L5a) using L3 qual + L1 data |
| Ch20: Integrity | voh_framework.md — scores assessed per-bank by Vice (L5a) using L3 qual integrity_flags |
| Ch21: Management Quality | question_compass.md (Ch21) |
| Ch22: Strategy | question_compass.md (Ch22) |
| Ch23: ESG & Governance | question_compass.md (Ch23) |

## Methodology Version Tracking

When the upstream HBS methodology document is updated:
1. Review all formula definitions in `formula_graph.json` for threshold changes.
2. Review `voh_framework.md` for scoring methodology changes.
3. Review `voh_framework.md` for weight and rating criteria changes.
4. Update `methodology_version` field in `formula_graph.json`.
5. Review `question_compass.md` for new or restructured chapters.

## Key Methodology Concepts

### Toolbox Model (not Checklist)

The HBS methodology advocates a "toolbox" approach rather than a "checklist" approach. AI spawns hold analytical tools (formulas, question guides, search strategies) and apply them autonomously based on what they discover — rather than mechanically ticking through every item. This is reflected in:
- L1: formula_graph as a dependency graph (compute what inputs allow), not a checklist
- L3: question_compass as open-ended questions, not yes/no items
- L2: on-demand search based on L1 curiosity, not batch scraping

### Mosaic Theory

Signals from disparate sources (financial statements, MD&A text, external intelligence) are pieced together to form a coherent picture — like a mosaic. No single signal is conclusive, but multiple signals pointing in the same direction create confidence. This is implemented in:
- L1: Merged quantitative + text diff in one spawn for real-time cross-validation
- L2: Edge signal search that explicitly maps findings to L1 flags (corroborates/contradicts)
- L4 removed v2026-06: Integrity assessment per-bank by Vice (L5a), cross-bank patterns by Chief (L5b)
- L5: Weighted judgment across all upstream markers

### Audit Trail

Every determination must be traceable to its source. The `analysis_trail.md` deliverable provides per-bank, per-layer traceability:
- Which metrics drove the VOH score
- Which text passages informed qualitative findings
- Which accounting comparisons drove integrity deductions
- Which edge signals corroborated or contradicted L1 flags
