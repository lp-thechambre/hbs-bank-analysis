# Edge Cases — HBS-Screen

> Known edge cases and how the pipeline handles them.

## Data Quality Edge Cases

### EC1: All Q1 fields null for a bank
**Scenario**: Bank has published annual report but not Q1 report. Most fields return null from API.
**Expected behavior**: Bank passes Phase 1 if annual data exists (single fetch per bank, latest non-null). If truly all null, R5 triggers (missing critical fields).
**Test**: Mock API response with all null values → verify REJECT with R5.

### EC2: CET1 present but NPL missing
**Scenario**: Inconsistent data — capital adequacy reported but asset quality missing.
**Expected behavior**: CET1 check runs, NPL check skipped (no crash). Bank passes Phase 1. In Phase 2, D2 scored with NPL N/A.
**Test**: Remove NPL from a passed bank's record → verify D2 reflects N/A.

### EC3: Negative BPS
**Scenario**: Bank has negative book value per share (rare, distressed bank).
**Expected behavior**: PB calculation skipped (BPS ≤ 0). D5 scored without PB sub-indicator.
**Test**: Set BPS to -1.0 → verify PB score is null, D5 uses DPR + EPS yield only.

### EC4: Extreme NPL (> 10%)
**Scenario**: Deeply distressed bank.
**Expected behavior**: F2 REJECT flag triggers (2σ outlier). R2 rejection if > 3.0%.
**Test**: Set NPL to 12% → verify R2 REJECT in Phase 1.

### EC5: Interest income ratio exactly at boundary (40%, 60%)
**Scenario**: Bank has exactly 40% or 60% interest income ratio.
**Expected behavior**: 60% → traditional_commercial (rule: > 60%). 40% → trading_ib (rule: ≤ 40%).
**Test**: Set ratio to 0.60, 0.40 → verify correct classifications.

## API Edge Cases

### EC6: API returns HTTP 500
**Scenario**: Eastmoney API down or rate-limited.
**Expected behavior**: 3 retries with exponential backoff. After exhaustion, report error, exit with code 1.
**Test**: Mock 500 response → verify retry count and final error exit.

### EC7: API returns 200 but empty data
**Scenario**: Valid HTTP response but `result.data` is null.
**Expected behavior**: `extract_records` returns None. Script exits with error.
**Test**: Mock {"success": true, "result": {"data": null}} → verify error exit.

### EC8: API response has unexpected field types
**Scenario**: Field returns string "-" or "" instead of null or number.
**Expected behavior**: `normalize_record` converts to None. No crash.
**Test**: Inject "-" values → verify normalized to None.

## Pipeline Edge Cases

### EC9: All 42 banks pass Phase 1
**Scenario**: Exceptional quarter — all banks meet thresholds.
**Expected behavior**: All 42 proceed to Phase 2. Trigger count may exceed 10 → capped at 10.
**Test**: Set all mock values above thresholds → verify 42 passed, triggers capped.

### EC10: Only 2 banks pass Phase 1
**Scenario**: Severe crisis quarter — most banks fail CET1 or NPL.
**Expected behavior**: 2 banks proceed to Phase 2. Final candidates = min(2, 15).
**Test**: Set most CET1 < 8.5% → verify few passed, pipeline completes.

### EC11: Phase 2 returns < 5 banks
**Scenario**: Multiple rejections in Phase 2 flags.
**Expected behavior**: Phase 3 triggers all remaining banks. Final output has < 5 candidates.
**Test**: Apply REJECT flags to most banks → verify graceful handling of small candidate set.

### EC12: Price data completely unavailable
**Scenario**: Both Eastmoney quote API and AKShare fail.
**Expected behavior**: D5 scored without PB and EPS yield (DPR only if available). Warning in output.
**Test**: Provide null prices → verify D5 partial scoring.

## Score Edge Cases

### EC13: All banks in a type group have identical values
**Scenario**: All traditional_commercial banks have the same CET1 (unrealistic but possible in mock).
**Expected behavior**: Linear scoring returns 50 for all (min == max → constant midpoint).
**Test**: Set all CET1 to 12% → verify all D1 CET1 scores = 50.

### EC14: Bank with perfect scores across all dimensions
**Scenario**: Top-performing bank is best in class for every metric.
**Expected behavior**: Score near 100 but capped by peer-group max values.
**Test**: Set all metrics to peer group maximums → verify scores near 100.

### EC15: Composite score ties between banks at cutoff
**Scenario**: Two banks have identical composite scores at the 12/13 boundary.
**Expected behavior**: Both included if within natural gap. Gap detection finds split point.
**Test**: Set scores equal at rank 12-13 → verify both included or gap logic handles it.

## ARCHITECTURE-v1 Pipeline Edge Cases

### EC16: Embedding API unavailable
**Scenario**: Qwen3-Embedding-0.6B at localhost:8000 is down or not deployed.
**Expected behavior**: `generate_embeddings.py` outputs cluster_report.json with `status: "error"` and empty clusters/outliers. Pipeline proceeds without clustering. Edge spawn skips cluster-based anomaly detection, focuses on metric-extreme and metric-mismatch types.
**Test**: Stop embedding service, run pipeline → verify cluster_report.json has error status, pipeline completes.

### EC17: Cluster report is empty
**Scenario**: Embedding API succeeded but clustering produced no meaningful clusters (all banks in one cluster).
**Expected behavior**: Edge spawn treats all banks as one cluster. Outlier detection still works via metric extremes. Synthesis spawn proceeds normally.
**Test**: Mock cluster_report.json with 1 cluster of 42 banks → verify edge spawn output is still meaningful.

### EC18: One spawn layer fails completely
**Scenario**: Quant spawn times out or crashes. Edge spawn succeeds.
**Expected behavior**: Scheduler logs the failure, proceeds with edge markers only. Qualitative spawns run on all banks. Synthesis has degraded input but can still make decisions.
**Test**: Force quant spawn to fail → verify pipeline continues with edge + qual + synthesis.

### EC19: Conflicting markers between layers
**Scenario**: Quant says PASS, Edge says high-severity anomaly, Qual says WATCH for the same bank.
**Expected behavior**: Synthesis classifies as CONFLICT (Pattern C). Reads the card (1 card read). Resolves based on anomaly severity and qual note quality. Bank may be included with caution flag.
**Test**: Create mock markers with deliberate conflicts → verify synthesis resolves without re-scoring.

### EC20: All banks unanimous — no conflicts
**Scenario**: Every bank has identical status across Quant, Edge, and Qual layers.
**Expected behavior**: Synthesis auto-classifies all banks. HIGH_CONFIDENCE_PASS banks go to candidates (top 15 by score). UNANIMOUS_REJECT banks eliminated. No card reads needed (0/5 budget used).
**Test**: Mock all markers in agreement → verify synthesis output has 0 card reads, 0 overrides.

### EC21: Too many conflict banks (>20)
**Scenario**: More than 20 banks have mixed signals between layers.
**Expected behavior**: Synthesis prioritizes conflicts: Pattern D (Quant REJECT + Qual PASS) first, then Pattern B (Quant PASS + Qual WATCH), then Pattern A, then Pattern C. Max 5 card reads. Remaining conflicts resolved conservatively (default to qual assessment).
**Test**: Mock 25 banks with various conflicts → verify synthesis handles within budget.

### EC22: Fewer than 10 banks pass all layers
**Scenario**: Only 6 banks get HIGH_CONFIDENCE_PASS. After conflict resolution, total is 8.
**Expected behavior**: Synthesis relaxes criteria. Re-examines UNANIMOUS_REJECT banks with weakest rejection reasons. Marks borderlines as "included to meet minimum (10)". Final candidates >= 10.
**Test**: Mock only 8 surviving banks → verify synthesis fills to 10.

### EC23: Card file missing for a bank
**Scenario**: One bank's .md card file wasn't generated or was deleted.
**Expected behavior**: Scheduler logs the missing card. Quant and Qual spawns mark the bank as WATCH with low confidence. Synthesis may include or exclude based on other markers.
**Test**: Delete one card file post-generation → verify pipeline handles gracefully.

### EC24: Scheduler spawn itself times out
**Scenario**: The scheduler spawn exceeds the 20-minute pipeline budget.
**Expected behavior**: Main session's cron watchdog fires. Checks scheduler status. If Layer 0 completed, runs `compute_scores.py --mode finalize` as fallback to produce best-effort output. Reports degraded result to user.
**Test**: Set artificially short timeout (2 min) → verify fallback triggers and produces partial output.

