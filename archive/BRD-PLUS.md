# BRD-PLUS: HBS-Screen v0.4

> **银行股初筛 Skill — 需求规格说明书（面向 AI 开发者）**
>
> 版本: v0.4 | 状态: 冻结 | 下游: Claude Code (DeepSeek v4 Pro) | 审查: 上尉
>
> 阅读指引：
> - **第 1-4 章**：必须遵守的硬约束（雷区已标注）
> - **第 5 章**：AI 自主设计空间
> - **第 6 章**：验收标准
> - **第 7 章**：开源预备
> - **附录 A**：给 Claude Code 的 Prompt

---

## 1. 任务概述

### 1.1 这是什么

HBS-Screen 是银行股投研系统（HBS, Hermes Banking Stock）的第一层漏斗。它的唯一使命：

> **从 42 家 A 股上市银行中，筛选出 10-15 家有潜力进入深度分析（Depth）阶段的候选银行。**

### 1.2 这不是什么

- ❌ 不是独立分析工具——不产出投资建议
- ❌ 不是深度研究——不做管理层评估、不做估值建模、不做压力测试
- ❌ 不是数据看板——不提供可视化界面
- ✅ 是一个纯程序化筛选管道，输入代码列表，输出排序后的候选名单

### 1.3 核心设计原则

1. **少即是多**：Screen 只做 Screen 该做的事。克制。
2. **数据可得性优先**：拿不到的字段标注 N/A，不崩溃。
3. **可复现**：同一份输入 → 同一份输出。
4. **可审计**：每个银行进/出的理由可追溯。

### 1.4 产物形式

这是一个 **OpenClaw Skill**，目录结构：

```
bank-screen/
  SKILL.md              # Skill 入口（触发词、使用说明、spawn 编排指令）
  scripts/              # 数据获取脚本（东方财富 API 调用、PB 计算等）
  references/           # 参考文档（评分规则、字段映射表、银行列表）
  assets/               # 输出模板（候选名单 JSON schema）
```

SKILL.md 是入口，用户说「跑一下银行初筛」，Skill 触发，启动调度 spawn。

---

## 2. 架构硬约束（必须遵守）

> ⚠️ 以下每条都是雷区，踩中任意一条即判定为设计缺陷。

### 2.1 主 Session 隔离

```
硬规则：
- 主 session 不得接收任何财务数据、银行名称、分析结果。
- 主 session 只接触元状态：Phase N 完成/失败、进度百分比、超时告警。
- 所有分析逻辑在 spawn session 中执行。
- 所有数据获取在 spawn session 中执行。
- 调度 spawn 独立编排，不与主 session 共享上下文。
```

**为什么**：主 session 有 persona 设定（Nerv 指挥官）、记忆（MEMORY.md）、历史对话。这些内容会污染银行分析，且不同 session 的分析结果不可复现。

**主 session 的合法操作**：
- 接收司令官的「跑一下银行初筛」指令
- 发起调度 spawn（sessions_spawn）
- 设置超时 cron
- 接收调度 spawn 的完成通知（仅元数据，如「完成，12 家候选」「Phase 2 超时」）
- 展示最终候选名单给司令官
- 在超时/异常时执行 fallback 决策

### 2.2 三阶段管道

```
Phase 1: 定量粗筛
  输入：42 家银行代码列表
  输出：通过的银行（预估 25-30 家）+ 淘汰银行及理由
  目的：用极简指标排除明显不合格银行

Phase 2: 定量评分 + 定性标记
  输入：Phase 1 通过名单
  输出：维度评分 + Curiosity Flags + 综合排序
  目的：对所有通过银行做完整评分和标记，不做淘汰

Phase 3: 补充侦查 + 边缘信号 + 好奇心审查（触发式）
  触发：Phase 2 中满足触发规则的银行（预估 5-10 家）
  输出：final_candidates（10-15 家）+ analyst_notes
  目的：对有疑点的银行做定向搜索，消除边界不确定性
```

**阶段不可跳过，不可合并。Phase 3 仅对满足触发条件的银行执行。**

### 2.3 Spawn 隔离

```
- Phase 1 在独立 spawn 中执行
- Phase 2 可将银行按类型分组，每组在独立 spawn 中执行（可并行）
- Phase 3 对每家触发银行在独立 spawn 中执行（可并行）
- 调度 spawn 不执行任何分析逻辑，只负责编排和结果汇总
- 每个 spawn 的 prompt 仅包含：该阶段规则 + 目标银行数据 + 上一阶段输出摘要
- 不注入 SOUL.md、MEMORY.md、对话历史到分析 spawn
```

### 2.4 容错：双层监控

```
正常路径：
  主 session → 调度 spawn → Phase 1 → Phase 2 → Phase 3 → final_candidates

调度 spawn 在每个 Phase 完成后向主 session 发送进度通知：
  sessions_send(主session, "Phase 1 done: 28/42 passed")
  sessions_send(主session, "Phase 2 done: scored 28 banks")
  sessions_send(主session, "Phase 3 done: final 12 candidates")

超时监控：
  主 session 发起调度 spawn 时，同时设置 cron job：
    schedule: at（now + 预估总时间 × 1.5）
    payload: systemEvent "检查调度 spawn 状态，未完成则执行 fallback"

Fallback 策略（由 AI 自主设计具体逻辑，但必须覆盖）：
  - Phase 1 超时 → 减少银行数量（仅覆盖大行+股份行）重试
  - Phase 2 超时 → 跳过 Phase 2 直接进入 Phase 1 结果排序
  - Phase 3 超时 → 跳过 Phase 3，用 Phase 2 排序结果作为 final_candidates
  - 全部失败 → 通知司令官，建议手动介入
```

---

## 3. 数据源约束

### 3.1 主数据源：东方财富 F10 财务分析 API

```
Endpoint:
  https://datacenter.eastmoney.com/api/data/v1/get

参数：
  reportName=RPT_F10_FINANCE_MAINFINADATA
  columns=SECUCODE,SECURITY_NAME_ABBR,REPORT_DATE,{需要的字段}
  filter=(SECURITY_TYPE_CODE="058001001")(ORG_TYPE="银行")
  pageSize=50
  sortColumns=REPORT_DATE
  sortTypes=-1
```

### 3.2 已确认可用字段 → Screen 字段映射

| Screen 需求 | API 字段名 | 中文名 | 可用性 | 备注 |
|------------|-----------|--------|--------|------|
| CET1 | `HXYJBCZL` | 核心一级资本充足率 | ✅ | 部分银行 Q1 为 null，取最新非空值 |
| NPL 比率 | `NONPERLOAN` | 不良贷款率 | ✅ | 全覆盖 |
| NPL 余额 | `NON_PERFORMING_LOAN` | 不良贷款余额 | ✅ | 覆盖率计算用 |
| ROE | `ROEJQ` | ROE（季报年化） | ✅ | 全覆盖 |
| PCR | `BLDKBBL` | 拨备覆盖率 | ✅ | 全覆盖 |
| 总资产 | `TOTAL_ASSETS_PK` | 总资产 | ✅ | 全覆盖 |
| BPS | `BPS` | 每股净资产 | ✅ | PB 计算用 |
| EPS | `EPSJB` | 每股收益 | ✅ | 全覆盖 |
| 净利润 | `PARENTNETPROFIT` | 归母净利润 | ✅ | 覆盖率和 ROE 验算用 |
| 贷款总额 | `GROSSLOANS` | 贷款总额 | ✅ | 全覆盖 |
| 贷款拨备率 | `LOAN_PROVISION_RATIO` | 贷款拨备率 | ✅ | 辅助 D2 |
| 成本收入比 | `REVENUE_RATIO` | 成本收入比 | ⚠️ | 约 70% 银行有值 |
| NIM | `NET_INTEREST_MARGIN` | 净息差 | ⚠️ | 约 60% 银行有值，Q1 常缺失 |
| 资本充足率 | `NEWCAPITALADER` | 资本充足率 | ✅ | 辅助 D1 |
| 一级资本充足率 | `FIRST_ADEQUACY_RATIO` | 一级资本充足率 | ✅ | 辅助 D1 |

### 3.3 已确认不可用字段（不要在 Screen 阶段尝试采集）

| 字段 | 原因 |
|------|------|
| 逾期率 (`OVERDUE_LOANS`) | API 全部返回 null |
| 核销率 | API 无此字段 |
| 利息收入占比 | 需利润表分解，API 不含 |
| 存款成本率 | API 无此字段 |
| 分红数据 | 需分红专用 API（可后续补充，但 Phase 1 不用） |

**处理原则**：缺失字段标注 `N/A`，该子维度不参与评分。不因数据缺失崩溃、不因数据缺失淘汰银行。

### 3.4 需补充的数据源

| 缺失数据 | 替代方案（AI 自行选择实现） |
|---------|--------------------------|
| 股价（PB 计算用） | 东方财富行情 API / AKShare / 雪球 API |
| 分红数据（DPR 计算用） | 东方财富分红 API / 年报快报 |
| 利息收入占比（类型判定用） | 东方财富利润表 API 或估算 |

> 补充数据源的选择由 AI 自主决定。标准：稳定 > 速度 > 覆盖度。

---

## 4. 领域约束（银行股知识，AI 可能不知道）

> ⚠️ 以下每条是领域事实，不遵守会导致筛选结果失真。

### 4.1 PB 阈值不能用绝对值

```
错误做法：PB > 1.5 标记、PB < 0.5 淘汰
正确做法：使用同类型银行分位数

原因：中国银行板块长期处于 PB < 1 状态，42 家中 PB > 1 的可能不到 5 家。
      绝对阈值在绝大多数时间不会触发，失去了筛选意义。

建议：PB > 同类型 90 分位 → 标记 curiosity
      PB < 同类型 10 分位 + 资产质量差 → REJECT
```

### 4.2 银行类型分流

```
在 Phase 1 或 Phase 2 开始前，判定每家银行的类型：

  IF 利息收入占比 > 60% → 传统商业银行（NIM 为核心指标）
  IF 40% < 利息收入占比 ≤ 60% → 综合型银行（弱化 NIM）
  IF 利息收入占比 ≤ 40% → 交易型/投行型银行（强化非息收入）

类型影响：
  - D3 盈利能力维度的子指标权重分配
  - 传统银行：NIM 权重高
  - 交易型银行：NIM 权重低，非息收入权重高
  - Curiosity Flags 的阈值基准（同类型比较）

如利息收入占比不可得，用「手续费及佣金收入占比」近似替代。
```

### 4.3 RORWA 重要性

```
ROE 可以被杠杆放大——低资本充足率的银行 ROE 虚高。
RORWA（净利润/平均风险加权资产）消除杠杆扭曲。

建议在 D3 中同时使用 ROE 和 RORWA，或至少标注「高 ROE 低 RORWA」为 curiosity。
```

### 4.4 分红韧性（冲击年份行为）

```
核心判据：冲击年份反而提高分红，CET1 逼近监管红线 → 管理层短视。

Screen 阶段因数据限制，仅考察单年度（最近年报）：
  - DPR < 15% 且盈利正常 → REJECT（积累型银行，无分红价值）
  - DPR > 60% → WATCH（不可持续）
  - 每股分红同比下降 > 30% → WATCH（信号恶化）

历史冲击年份分析留给 Depth 阶段。
```

### 4.5 核销率是隐藏坏账探测器

```
核销金额增速 > 不良余额增速 → 不良被核销对冲，真实风险在积聚。

Screen 阶段因 API 无此字段，不做采集。但在 Curiosity Flag 中预留位置（F-NCO），
如未来数据可用则激活。
```

### 4.6 房地产敞口不在 Screen 阶段评估

```
原因：
  1. 关联行业识别（建筑、建材、钢铁等）需要深度数据
  2. 各银行披露口径不一致，无法标准化比较
  3. 不准确的数据标记会造成噪音

结论：Screen 不评估房地产风险。留给 Depth。
```

---

## 5. AI 自主设计空间

> 以下领域由实现 AI 自主决策。本节仅提供指导性原则和建议方向。

### 5.1 分批/并行策略（完全自主）

```
设计空间：
  - Phase 1 是 42 家一次跑完还是分批？
  - Phase 2 按银行类型分几组？每组几家？
  - Phase 2 的组是串行还是并行？
  - Phase 3 触发银行是逐个还是批量处理？

指导原则：
  - 单个 spawn 的上下文窗口控制在 15 家银行以内为最佳
  - 并行 spawn 数量不超过 5，避免 rate limit
  - 推荐：Phase 1 全局一次 | Phase 2 按类型 3 组并行 | Phase 3 逐个
```

### 5.2 评分公式（完全自主）

```
需要 AI 自主定义的内容：
  - Phase 1 粗筛的具体阈值（CET1 < ? → REJECT，NPL > ? → REJECT）
  - Phase 2 五个维度各自的子指标权重
  - 连续指标到 0-100 分的映射方式（分位数映射？线性映射？分段？）
  - 五个维度到综合得分的聚合方式（等权？加权？）
  - 综合排序公式

指导原则：
  - 评分必须可复现（确定性公式，无随机性）
  - 所有阈值需要标注依据（如「监管红线 + 1% 缓冲」或「行业均值 + 2σ」）
  - 不同类型银行的评分基准应使用同类型分位数，而非全局分位数
```

### 5.3 Curiosity Flags 触发规则（完全自主）

```
Phase 2 需要定义 8-12 个 Curiosity Flag，每个包含：
  - Flag 名称和描述
  - 触发条件（精确到可编程）
  - 级别：WATCH（关注）/ REJECT（淘汰候选）/ INFO（信息标注）

REJECT 级 Flag 直接将该银行从候选名单移除。
WATCH 级 Flag 在 Phase 3 中作为补充侦查的触发条件。

参考 Flag（实现者可增减）：
  F1: CET1 逼近监管红线 + 1% 以内
  F2: NPL 与同业偏差超过 +2σ
  F3: 逾期率-不良率差值异常（如数据可用）
  F4: 成本收入比趋势恶化（连续 2 年上升 > 5pp）
  F5: 管理层近期变动（年报披露）
  F6: DPR 不可持续（> 60%）
  F7: 每股分红同比下降 > 30%
  F8: NIM 同比下降 > 30bp
  F9: 高 ROE 低 RORWA（杠杆虚高）
  F-NCO: 核销率异常（预留，未来数据可用时激活）
```

### 5.4 Phase 3 触发规则（逻辑由 AI 定义）

```
Phase 3 的触发规则需要 AI 自主定义，必须平衡过触发和欠触发。

推荐框架（AI 可调整）：
  A. 定量评分在 cutoff 线 ±5% 内的银行（边界银行，需更多信息）
  B. 触发 ≥2 个 WATCH 级 Curiosity Flag
  C. 出现定量与定性信号冲突的银行（如 ROE 高但 NPL 也高）
  D. 触发 ≥1 个 REJECT 级 Curiosity Flag（需确认是否误判）

预估触发 5-10 家。
```

### 5.5 错误处理与降级（完全自主）

```
需要 AI 自主设计的错误场景：
  - API 请求超时 → 重试次数？退避策略？
  - API 返回格式异常 → 跳过该银行？标记 N/A？
  - spawn 执行超时 → 降级策略？
  - 部分银行数据缺失严重 → 淘汰还是保留并标注？

指导原则：
  - 单个银行数据获取失败不应阻塞全局管道
  - 降级时保留足够信息供司令官判断
  - 所有异常必须记录到输出日志
```

### 5.6 调度 spawn 的实现（完全自主）

```
调度 spawn 的实现方式由 AI 自主选择：
  - 使用 TaskFlow 框架（推荐，已内建状态管理和超时）
  - 自行编排 sessions_spawn + sessions_yield

如使用 TaskFlow，参考 skill: taskflow。
```

---

## 6. 验收标准

### 6.1 功能验收

- [ ] F1: 给定 42 家银行代码列表，输出 10-15 家候选银行（JSON 格式）
- [ ] F2: 每家有明确的通过/淘汰理由，可追溯到具体指标
- [ ] F3: 同一份输入运行 3 次，得到相同的候选名单
- [ ] F4: 主 session 在执行过程中不接收任何财务数据或银行名称
- [ ] F5: Phase 1 执行时间 < 3 分钟
- [ ] F6: 全管道执行时间 < 15 分钟
- [ ] F7: API 调用全部失败时，产出明确错误报告而非崩溃

### 6.2 质量验收

- [ ] Q1: 候选名单中不包含 CET1 < 监管红线 + 0.5% 的银行
- [ ] Q2: 候选名单中不包含 NPL > 行业均值 + 2σ 的银行
- [ ] Q3: 不同类型银行（传统/综合/交易型）的评分基准使用了同类型分位数
- [ ] Q4: PB 阈值使用相对分位数，非绝对值
- [ ] Q5: 缺失数据字段标注 N/A，不影响整体评分流程

### 6.3 输出格式验收

```json
{
  "screen_run": {
    "id": "screen-2026-05-29-001",
    "timestamp": "2026-05-29T16:00:00+08:00",
    "data_source": "eastmoney_f10_api",
    "data_as_of": "2026Q1",
    "total_banks": 42,
    "phase1_passed": 28,
    "phase2_scored": 28,
    "phase3_probed": 7,
    "final_candidates": 12
  },
  "candidates": [
    {
      "code": "SH601328",
      "name": "交通银行",
      "type": "traditional_commercial",
      "score": 78.5,
      "rank": 1,
      "dimension_scores": {
        "D1_capital_preservation": 82,
        "D2_asset_quality": 75,
        "D3_profitability": 71,
        "D4_growth": 68,
        "D5_valuation": 85
      },
      "flags": ["F1: CET1 near redline"],
      "reasons": "D5估值安全边际突出...",
      "data_quality": {
        "completeness": 0.85,
        "missing_fields": ["NIM", "interest_income_ratio"],
        "confidence": "medium"
      }
    }
  ],
  "rejected": [
    {
      "code": "SH600015",
      "name": "华夏银行",
      "phase": 1,
      "reason": "CET1 below threshold: 8.97% vs 9.5% minimum",
      "dimension": "D1_capital_preservation"
    }
  ],
  "analyst_notes": "Phase 3 对 7 家边界银行进行了补充侦查...",
  "warnings": [
    "NIM data missing for 12 banks (Q1 reports)",
    "Interest income ratio estimated for 8 banks"
  ],
  "errors": []
}
```

> 以上 schema 为最低要求。AI 可扩展但不删减必填字段。

---

## 7. 开源预备

### 7.1 文件结构（含开源元数据）

```
bank-screen/
  SKILL.md                  # Skill 入口
  LICENSE                   # 开源许可证（建议 Apache 2.0 或 MIT）
  README.md                 # 项目说明（面向人类开发者）
  scripts/
    fetch_financials.py     # 东方财富 API 数据获取
    compute_scores.py       # 评分计算
    pb_fetcher.py           # PB 数据获取
  references/
    bank_list.md            # 42 家银行代码清单
    field_mapping.md        # API 字段 → Screen 字段映射
    scoring_rules.md        # 评分规则详细说明
    methodology.md          # 方法论引用（指向 HBS v0.3 相关章节）
  assets/
    output_schema.json      # 输出 JSON schema
    candidate_template.json # 候选名单模板
  tests/
    sample_output.json      # 预期输出示例
    edge_cases.md           # 边界 case 说明
```

### 7.2 SKILL.md 元数据

```yaml
---
name: bank-screen
description: "Screen A-share bank stocks for depth analysis candidates."
metadata:
  openclaw:
    emoji: "🏦"
    user-invocable: true
    allowed-tools: ["exec", "web_fetch", "sessions_spawn", "sessions_yield", "sessions_send", "cron"]
  homepage: "https://github.com/[org]/hermes-banking-stock"
  license: "Apache-2.0"
---
```

### 7.3 开源注意事项

- 方法论引用标注 HBS 版本号和章节，方便未来追溯
- 评分规则和阈值的**变更历史**记录在 `references/scoring_rules.md` 的 changelog 中
- 东方财富 API 的使用说明包含 rate limit 和免责声明
- README 明确说明：本 Skill 不构成投资建议
- 数据获取脚本应包含 user-agent 和合规的请求频率控制
- 预留接口便于未来扩展 depth、voh 等下游 Skill

### 7.4 与下游 Skill 的接口契约

```
Screen 的输出即 Depth 的输入。

为确保未来 Depth Skill 独立开发时的一致对接：

- Screen 输出的 candidate JSON 必须包含 depth_input 字段
- depth_input 包含 Depth 阶段所需的最小数据集（银行代码 + 数据时点 + Screen 评分摘要）
- 接口 schema 版本号（如 "screen_output_v1"）确保向前兼容
```

---

## 附录 A：给 Claude Code 的启动 Prompt

> 以下 Prompt 可直接发送给 Claude Code（以 DeepSeek v4 Pro 为大脑）。
> 建议在发送前确认 Claude Code 的工作目录已设置为本 skill 的仓库路径。

```
## Task

Implement the HBS-Screen Skill as defined in BRD-PLUS.md (this file).
Read BRD-PLUS.md first, then proceed.

## What to build

An OpenClaw Skill at `bank-screen/SKILL.md` with supporting scripts,
that screens 42 A-share bank stocks into 10-15 depth-analysis candidates.

The Skill uses a 3-phase spawn pipeline:
  Phase 1: Coarse quantitative filtering (42 → ~28)
  Phase 2: Full scoring + qualitative flags (~28 scored + flagged)
  Phase 3: Triggered deep probe on flagged banks (5-10 probed → 10-15 final)

## Rules

1. Follow ALL hard constraints in Chapter 2 (main session isolation,
   3-phase pipeline, spawn isolation, dual-layer monitoring).
2. Use the Eastmoney F10 API as primary data source (Chapter 3).
3. Respect ALL domain constraints in Chapter 4 (PB relative thresholds,
   bank type classification, RORWA, single-year DPR only).
4. You have full autonomy on the design areas in Chapter 5
   (batching, scoring formula, flag rules, phase-3 triggers, error handling).
5. Output must pass the acceptance criteria in Chapter 6.
6. Structure the skill per Chapter 7 for future open-source release.

## Deliverables

1. `SKILL.md` — Entry point, trigger, usage, spawn orchestration instructions
2. `scripts/` — Python/Node scripts for data fetching and scoring
3. `references/` — Bank list, field mapping, scoring rules, methodology refs
4. `assets/` — Output schema and templates
5. `README.md` — Human-readable project overview

## Non-goals

- No UI, no dashboard, no visualization
- No Depth analysis logic (that's a separate skill)
- No real-time streaming or websocket connections
- No database persistence beyond TaskFlow state

Start by reading BRD-PLUS.md in full, then plan your implementation before writing any code.
```

---

> **文档结束。**
>
> 审批：上尉 ✅ | 提交：司令官 | 下一阶段：Claude Code 实现
