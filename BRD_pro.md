# HBS-Screen 业务描述与架构规划 v1

> **Hermes Banking Stock — Screen Skill**
>
> 版本: v1.0 | 状态: 开发中 | 目标平台: OpenClaw
>
> 本文档是 HBS-Screen Skill 的权威业务描述与架构规划。所有实现必须以此文档为基准。

---

## 一、产品概述

### 1.1 这是什么

HBS-Screen 是 Hermes Banking Stock (HBS) 投研系统的**第一层漏斗**。它是一个安装在 OpenClaw 中的 AI Skill，唯一使命：

> 从 42 家 A 股上市银行中，筛选出 10-15 家值得进入深度分析（Depth）阶段的候选银行。

### 1.2 这不是什么

- 不是独立分析工具 — 不产出投资建议
- 不是深度研究 — 不做管理层评估、估值建模、压力测试
- 不是数据看板 — 不提供可视化界面
- 是一个纯程序化筛选管道：输入触发词，输出候选名单 + 审计底稿

### 1.3 核心设计原则

1. **少即是多**：Screen 只做漏斗，不做分析。克制。
2. **可审计**：每家银行进/出的理由可追溯到具体层级和指标。
3. **自愈能力**：数据源 API 变更时，AI 自动重新发现参数，不依赖人工维护。
4. **可复现**：确定性计算层（Python 脚本）+ AI 判断层（spawn）+ 冲突裁决层（synthesis）。

### 1.4 触发方式

用户在 OpenClaw 中说：

```
跑一下银行初筛
screen banks
银行股筛选
bank screen
```

Skill 启动调度 spawn，执行 4 层管道，最终产出三份交付物。

---

## 二、架构总览

### 2.1 四层 Spawn 拓扑

```
                        ┌──────────────────────────┐
                        │     Layer 0: 数据工程       │
                        │  AI API 发现 + Python 拉取  │
                        │  42 张银行卡片 + index.csv  │
                        └──────────────────────────┘
                                     │
                                     ▼
              ┌──────────────────────────────────────────────┐
              │              调度 Spawn (Scheduler)           │
              │  隔离运行，主 session 仅触发并立即恢复          │
              │  层间数据通过磁盘文件传递，不靠上下文            │
              └──────────────────────────────────────────────┘
                                     │
                         ┌───────────┼───────────┐
                         ▼           ▼           ▼
                 ┌───────────┐ ┌───────────┐ ┌───────────┐
                 │ 定量 Spawn │ │边缘 Spawn │ │定性 Spawn  │
                 │ (1 个,    │ │ (1 个,    │ │ (3-4 个,  │
                 │  并行)    │ │  并行)    │ │  并行)    │
                 └───────────┘ └───────────┘ └───────────┘
                         │           │           │
                         └───────────┼───────────┘
                                     ▼
                          ┌──────────────────┐
                          │   统合 Spawn      │
                          │  裁判 + 冲突裁决   │
                          │  → 输出 10-15 家  │
                          └──────────────────┘
                                     │
                                     ▼
                         主 session 收到完成通知
```

### 2.2 层级职责

| 层 | 名称 | 执行者 | 输入 | 输出 |
|----|------|--------|------|------|
| L0 | 数据工程 | 调度器 + Python 脚本 | Eastmoney API (web_fetch 发现, requests 拉取) | raw JSON + index.csv + 42 张 .md 卡片 |
| L1 | 定量 + 边缘 | 2 个并行 AI spawn | index.csv + 卡片 | quant_markers.json + edge_markers.json |
| L2 | 定性 | 3-4 个并行 AI spawn | 卡片 + L1 标记 | qual_markers_{group}.json |
| L3 | 统合 | 1 个 AI spawn | 所有 markers | final_output.json + screening_report.md |

调度器在 L3 完成后编译 `analysis_trail.md`。

### 2.3 硬约束（不可违反）

1. **主 Session 隔离**：主 session 不得接收任何财务数据、银行名称或分析结果。只接触元状态。
2. **文件传递**：所有数据以文件形式存储在 `data/` 下。层间传递文件路径，不传数据。
3. **层不可跳过**：四层必须依次执行，但某层失败时可以降级输入继续。
4. **统合是裁判**：L3 不重新打分，只做交叉判定和冲突裁决。
5. **路径约束**：所有产出物必须在 `data/YYYY-MM-DD/` 下。

---

## 三、Layer 0: 数据工程（混合模式）

### 3.1 设计理念

Layer 0 采用 **AI 发现 + Python 执行** 的混合架构：

- **AI (web_fetch)**：浏览东方财富页面，发现 API endpoint、字段映射、过滤器参数。写入 `api_profile.json`。
- **Python (requests)**：读取 `api_profile.json`，执行可靠的大批量数据拉取、重试、归一化。

AI 做它擅长的事（理解网页结构、适应变化），Python 做它擅长的事（稳定 HTTP 拉取、确定性计算）。

### 3.2 自愈机制

```
每次运行:
  检查 data/api_profile.json
    ├─ 存在且未过期 (< 30 天) → 直接使用
    ├─ 过期 → web_fetch 重新浏览东方财富页面 → AI 发现新参数 → 更新 profile
    └─ 发现失败 → 回退 Python 脚本硬编码默认值
```

东方财富改 API 时，30 天内 profile 过期 → AI 自动重新发现 → 管道自愈。用户无需修改任何代码。

### 3.3 数据源

| 数据 | API | 方式 |
|------|-----|------|
| 主要财务指标 | `datacenter.eastmoney.com/api/data/v1/get` (RPT_F10_FINANCE_MAINFINADATA) | Python `requests.get` |
| 利润表 | 同上 (RPT_F10_PROFIT_STATEMENT) | 同上 |
| 分红数据 | 同上 (RPT_F10_DIVIDEND) | 同上 |
| 股价 | `push2.eastmoney.com/api/qt/stock/get` | 同上 |

全部为公开 API，无需认证。

### 3.4 index.csv 格式

每行 ~50 tokens，确保任何模型都能将整个 index 常驻上下文。

```
code,name,type,pb,roe,npl,car,nim,mcap_rank
600036,招商银行,integrated,0.72,10.8,0.95,16.3,2.12,1
601398,工商银行,traditional_commercial,0.55,11.2,1.25,17.8,1.89,2
...
```

### 3.5 银行卡片格式

每张卡片 ~1000-1500 tokens，Markdown 格式，包含：
- 基本概况（类型、总资产、BPS、EPS）
- 核心财务指标表（CET1、CAR、NPL、PCR、ROE、NIM、成本收入比）
- 市场数据（PB、股价、EPS Yield、DPR、DPS）
- 快速评估（资本/资产质量/盈利/估值各 1-2 句）
- 数据质量（完整性百分比、缺失字段列表）

---

## 四、Layer 1-3: AI Spawn 设计

### 4.1 定量 Spawn (Quant)

**角色**：只跟数字对话。看 index.csv + 按需读取卡片，识别指标组合中的模式。

**输入**：
- 常驻上下文：index.csv（~2100 tokens）
- 按需读取：银行卡片（最多 15-20 张）

**输出**：`quant_markers.json` — 42 家银行，每家标注：

| 字段 | 说明 |
|------|------|
| status | PASS / WATCH / REJECT |
| confidence | high / medium / low |
| curiosity | 不超过 100 字的好奇心标记 |

**硬阈值**：

| 指标 | REJECT | WATCH |
|------|--------|-------|
| CET1 | < 8.5% | < 9.5% |
| NPL | > 3.0% | > peer mean + 1.5σ |
| ROE | < 0% | < 5% |
| CAR | — | < 12% |
| NIM | — | < 1.0% |

### 4.2 边缘信号 Spawn (Edge)

**角色**：全局视野，专找偏离正常模式的银行。与定量 spawn 并行运行，互不可见对方结果。

**异常类型**：

| 类型 | 说明 |
|------|------|
| `metric_extreme` | 单一指标偏离全 42 家分布 >2σ |
| `metric_mismatch` | 两个应相关的指标出现矛盾（如高 ROE + 高 NPL） |
| `group_outlier` | 银行指标与其声明的类型不符 |
| `trend_break` | 指标方向性转变（标记 INFO，需历史数据） |

**输出**：`edge_markers.json` — 每个异常包含 code、anomaly_type、severity、description。

### 4.3 定性 Spawn (Qual, 3-4 个并行)

**角色**：按银行类型分组（traditional_commercial / integrated / trading_ib），做组内横向比较。回应 L1 的好奇心标记。

**分组规则**：
- 每组 4-8 家银行
- 超过 8 家的组按市值排名拆分为两半
- 每组独立 spawn，prompt 根据组类型定制

**输出**：`qual_markers_{group}.json` — 每家银行包含 assessment (PASS/WATCH/REJECT)、note、upstream_flags_responded_to、group_rank。

### 4.4 统合 Spawn (Synthesis)

**角色**：裁判。不重新分析数据，只做交叉判定和冲突裁决。

**工作流**：

1. 读取全部 markers → 自动分为三组：
   - **HIGH_CONFIDENCE_PASS**：Quant PASS + Qual PASS → 直接入选
   - **UNANIMOUS_REJECT**：Quant REJECT + Qual REJECT → 直接淘汰
   - **CONFLICT**：各方意见不一致 → 需要裁决

2. 按冲突模式批量处理：
   - **Pattern A**：Quant WATCH + Qual PASS → 信任定性（有完整卡片上下文）
   - **Pattern B**：Quant PASS + Qual WATCH/REJECT → 信任定性（做了同业比较）
   - **Pattern C**：Edge 异常 + 双方 PASS → 检查异常严重度
   - **Pattern D**：Quant REJECT + Qual PASS → 硬阈值优先，最多读 3 张卡片确认

3. 输出 10-15 家最终候选 + 筛选报告

---

## 五、评分与标记体系

### 5.1 五维度评分

| 维度 | 权重 | 核心指标 |
|------|------|---------|
| D1 资本保全 | 25% | CET1、CAR、一级资本充足率 |
| D2 资产质量 | 25% | NPL、拨备覆盖率、贷款拨备率 |
| D3 盈利能力 | 20% | ROE、RORWA、NIM（权重按银行类型调整） |
| D4 成长性 | 15% | 资产规模百分位 |
| D5 估值回报 | 15% | PB、DPR、EPS Yield |

所有评分使用**同类型银行分位数**，不用绝对值。PB 阈值使用相对分位数而非固定值。

### 5.2 银行类型分类

基于利润表中 `利息净收入 / 营业总收入`：

| 比值 | 类型 | D3 特征 |
|------|------|---------|
| > 60% | traditional_commercial | NIM 权重高 |
| 40%-60% | integrated | NIM 与非息收入均衡 |
| ≤ 40% | trading_ib | 非息收入权重高，NIM 权重为 0 |

### 5.3 好奇心标记 (Curiosity Flags)

| ID | 名称 | 级别 | 触发条件 |
|----|------|------|---------|
| F1 | CET1 边际紧张 | WATCH | CET1 < 9.5% |
| F2 | NPL 异常值 | REJECT | NPL > 同行均值 + 2σ |
| F3 | 拨备不足 | WATCH | 120% ≤ PCR < 160% |
| F4 | NIM 临界 | WATCH | NIM < 1.0% |
| F5 | 杠杆虚高 ROE | WATCH | ROE > p75 且 ROA < 0.3% |
| F6 | DPR 不可持续 | WATCH | DPR > 60% |
| F8 | 成本收入比高 | INFO | > 60% |
| F9 | 盈利能力担忧 | INFO | ROE < 5% |
| F10 | 资本缓冲薄 | WATCH | CAR < 12% |
| F11 | 数据质量差 | INFO | >1 个关键字段缺失 |

---

## 六、产出物

每次运行产出**三份交付物**，全部位于 `data/YYYY-MM-DD/`：

| 文件 | 格式 | 生成者 | 读者 |
|------|------|--------|------|
| `final_output.json` | JSON | Synthesis spawn | 下游 Depth Skill |
| `screening_report.md` | Markdown | Synthesis spawn | 人类分析师 |
| `analysis_trail.md` | Markdown | Scheduler | 审计/复核 |

### 6.1 final_output.json

结构化 JSON，包含：
- `screen_run`：运行元数据（ID、时间戳、数据时点、完成层级、管道版本）
- `candidates`：候选银行列表（排名、得分、维度得分、标记、source_tracking）
- `rejected`：淘汰银行列表（淘汰层级、原因、关键指标）
- `depth_input`：下游 Depth Skill 接口字段
- `analyst_notes`、`warnings`、`errors`

### 6.2 screening_report.md

人类可读的 Markdown 报告：
- 执行摘要
- 候选银行排名表 + 详情（含审计轨迹摘要）
- 淘汰银行表
- 数据质量摘要
- 方法论备注
- 免责声明

### 6.3 analysis_trail.md

42 家银行完整的四层审计轨迹：
- 筛选决策汇总表
- 每家银行的逐层记录：L1 定量 → L1 边缘 → L2 定性 → L3 裁决
- 最终决定及理由

---

## 七、文件结构

```
bank-screen/
├── SKILL.md                          # Skill 入口、编排指令、产出物契约
├── README.md                         # 人类可读项目说明
├── LICENSE                           # Apache 2.0
├── .gitignore
│
├── prompts/                          # Spawn prompt 模板
│   ├── scheduler_prompt.md           # 调度器（编排 + API 发现 + 底稿编译）
│   ├── quant_spawn_prompt.md         # 定量分析
│   ├── edge_spawn_prompt.md          # 边缘信号检测
│   ├── qual_spawn_prompt.md          # 定性同业比较
│   └── synthesis_spawn_prompt.md     # 统合裁决 + 报告生成
│
├── scripts/                          # Python 数据工程脚本
│   ├── api_profile_loader.py         # API profile 共享加载器
│   ├── bank_constants.py             # 银行列表、阈值、权重常量
│   ├── fetch_financials.py           # 财务数据拉取（支持 --profile）
│   ├── pb_fetcher.py                 # 股价拉取（支持 --profile）
│   ├── generate_bank_cards.py        # 卡片 + index.csv 生成
│   ├── generate_embeddings.py        # [可选] 聚类分析
│   └── compute_scores.py             # [可选] 计分引擎回退
│
├── references/                       # 参考文档
│   ├── bank_list.md                  # 42 家银行代码清单
│   ├── field_mapping.md              # API 字段映射
│   ├── scoring_rules.md              # 评分规则详解
│   ├── methodology.md                # 方法论引用
│   └── embedding_upgrade_plan.md     # Embedding 集成方案
│
├── assets/                           # 模板与 Schema
│   ├── api_profile_template.json     # API 配置模板
│   ├── output_schema.json            # 输出 JSON Schema
│   └── candidate_template.json       # 输出样例
│
└── tests/                            # 测试
    ├── sample_output.json            # 预期输出示例
    └── edge_cases.md                 # 边界 case 文档
```

---

## 八、执行流程

### 8.1 正常路径

```
主 session 接收触发词
  → 验证环境: python3 --version, requests 可用
  → 创建数据目录: data/YYYY-MM-DD/cards/
  → 启动调度 spawn (prompts/scheduler_prompt.md)

调度 spawn 内部:
  L0: AI 发现/验证 api_profile.json → Python 脚本拉取 4 份数据
      → 生成 index.csv + 42 张卡片
  L1: 并行启动 quant spawn + edge spawn → 收集 markers
  L2: 按类型分组，并行启动 3-4 个 qual spawn → 收集 markers
  L3: 启动 synthesis spawn → final_output.json + screening_report.md
  L4: 编译 analysis_trail.md (调度器自行完成)

调度 spawn 通知主 session (仅元数据)
  → 主 session 展示结果摘要给用户
```

### 8.2 降级路径

| 故障 | 行为 |
|------|------|
| API profile 过期 | AI 重新 web_fetch 发现 → 更新 profile |
| API profile 发现失败 | 回退 Python 脚本硬编码默认值 |
| 某一数据源拉取失败 | 跳过该数据源，卡片中对应字段标 N/A |
| Quant spawn 超时 | 跳过，用 edge + qual 继续 |
| Edge spawn 超时 | 跳过，用 quant + qual 继续 |
| Qual spawn 超时 | 跳过该组，用 quant + edge 继续 |
| Synthesis spawn 超时 | 调度器自行生成降级报告 + 底稿 |
| 全管道超时 (30 min) | 产出已完成层级的最优结果 |

---

## 九、平台与依赖

### 9.1 目标平台

**OpenClaw**（优先）。适配其他框架只需映射工具名。

### 9.2 必需工具

| 工具 | 用途 |
|------|------|
| `exec` | 运行 Python 脚本、shell 命令 |
| `Read` | 读取数据文件 |
| `Write` | 写出 markers 和交付物 |
| `web_fetch` | AI 浏览页面发现 API 参数 |
| `sessions_spawn` | 启动分析 spawn |

### 9.3 运行时依赖

- Python 3.12+
- `pip install requests`
- 无需 API Key、无需数据库、无需 GPU

---

## 十、与下游 Skill 的接口

Screen 的输出即 Depth 的输入。`final_output.json` 中的 `depth_input` 字段提供：

- 候选银行代码 + 名称
- 数据时点
- 初筛评分摘要（含 source_tracking）
- Schema 版本号（向前兼容）

下游 Depth Skill 独立开发时，只需读取 `depth_input` 即可获取初筛结果。

---

## 十一、免责声明

本 Skill 仅供研究参考，不构成投资建议。所有评分和标记均为定量模型输出，不应作为买卖决策的唯一依据。投资决策应在咨询合格金融专业人士后做出。

---

> **文档结束。**
>
> 下一阶段：在 OpenClaw 中端到端测试全管道。
