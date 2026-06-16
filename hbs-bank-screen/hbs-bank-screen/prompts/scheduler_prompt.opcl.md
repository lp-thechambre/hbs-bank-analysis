# HBS-Screen: Analysis Trail Compilation Template (ARCHITECTURE-v2)

> This file is a **reference template** for the main session, not a spawn prompt.
> ARCHITECTURE-v2: The main session directly orchestrates all layers. No scheduler spawn.
> Use this template for Step 6 (Compile Analysis Trail) of the main session execution flow.

## Analysis Trail Template

Compile `{data_dir}/analysis_trail.md` — a single Markdown file recording every bank's screening journey through all 4 layers.

Generate this file from the main session. Read all marker files and final_output.json, then assemble the trail. This is metadata compilation, not analysis.

Template:

```
# HBS 银行股初筛 — 分析底稿

> 运行 ID: {id} | 生成时间: {timestamp} | 管道版本: ARCHITECTURE-v2
> 数据时点: {data_as_of} | 数据源: 东方财富 F10 API
> 完成层级: {layers_completed}

## 筛选决策汇总

| # | 代码 | 名称 | 类型 | L1定量 | L1边缘 | L2定性 | L3裁决 | 最终 |
|---|------|------|------|--------|--------|--------|--------|------|
| 1 | SH601398 | 工商银行 | 传统型 | PASS | — | PASS (r1) | HIGH_CONF | ✅ 候选 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

## 各家银行审计轨迹

### {代码} — {名称}

**银行概况**
- 类型: {type} | 数据质量: {从卡片提取}

**Layer 1 — 定量分析**
- 状态: {PASS|WATCH|REJECT} | 置信度: {high|medium|low}
- 好奇心标记: "{curiosity}"

**Layer 1 — 边缘信号检测**
- 异常详情: {每种异常的类型、严重度、描述, or "无异常"}
- 外部信号: {来自 web_search 的罚单/管理层/行业事件, or "无"}

**Layer 2 — 定性同业比较**
- 评估: {PASS|WATCH|REJECT} | 组内排名: {rank}/{group_size}
- 分析摘要: "{note}"
- 回应的上游标记: {upstream_flags_responded_to}

**Layer 3 — 综合裁决**
- 共识组: {HIGH_CONFIDENCE_PASS|UNANIMOUS_REJECT|CONFLICT}
- 冲突类型: {Pattern A/B/C/D, or "N/A (无冲突)"}
- 选择路径: {consensus|conflict_resolved|borderline_inclusion}
- 最终决定: {✅ 候选 / ❌ 淘汰 / ⚠️ 边界入选}
- 裁决理由: "{reasons}"

---
```

Repeat for ALL 42 banks. Verify:
- 42 banks in the summary table
- Every bank has all sub-sections filled

## Pipeline State Tracking

During the pipeline run, the main session maintains `{data_dir}/pipeline_state.json`:

```json
{
  "status": "layer0_complete|layer1_complete|layer2_complete|layer3_complete|done",
  "started_at": "ISO8601 timestamp",
  "layers_completed": ["L0", "L1"],
  "layer_times": {
    "L0": {"start": "...", "end": "...", "duration_s": 45},
    "L1": {"start": "...", "end": "...", "duration_s": 180}
  },
  "errors": [],
  "kpi_results": {
    "L1_quant": {"passed": true, "banks_assessed": 42, "watch_reject_count": 12},
    "L1_edge": {"passed": true, "anomalies_detected": 8, "high_severity_count": 3},
    "L2_qual": {"groups_completed": 5, "groups_total": 5, "banks_assessed_pct": 95},
    "L3_synthesis": {"candidates_selected": 12, "rejection_reasons_present": true}
  }
}
```

Progress is written to this file at each layer boundary. The user is NOT interrupted with progress notifications — only the final summary is reported.
