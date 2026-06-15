# HBS-Bank-Portfolio — Claude Code 项目指引

> **Platform note**: Primary development target is **OpenClaw**. This file documents Claude Code adaptation.
> See PLATFORMS.md for full platform compatibility matrix and tool name mappings.

## 项目定位

Homebrew Strategy (HBS) 三件套 Skill 的第三层：**组合构建层**。

```
hbs-bank-screen (L1)  →  hbs-bank-depth (L2)  →  hbs-bank-portfolio (L3)
    42 → 10-15 家            全量深度审计              跨行横评 + 权重分配
```

Portfolio 接收 Depth 产出的 10-15 家银行全量分析结果，核心工作是**跨行横评**——排雷、找金子、产出战略权重（长期持有）和战术权重（短期入场）。

**不做的事**: 筛选（Screen）、逐家审计（Depth）、Monte Carlo/二次规划（过度工程化）。

## 平台工具映射

Primary source: `SKILL.md` (OpenClaw format). Adapt tool names for Claude Code:

| OpenClaw | Claude Code | 用途 |
|----------|-------------|------|
| `exec` | `Bash` | Shell 命令 (Python 脚本, mkdir, date) |
| `Read` | `Read` | 文件读取 |
| `Write` | `Write` | 文件写入 |
| `web_fetch` | `WebFetch` | 网页抓取 |
| `web_search` | `WebSearch` | 网页搜索 |
| `sessions_spawn` | `Agent` | 启动 AI 子代理 (支持并行: 多个 Agent 调用同一条消息) |

**Depth limit**: Both platforms enforce subagent depth limit = 1. Subagents cannot spawn sub-sub-agents. SKILL.md's flat topology (main session → direct spawns) works on both platforms.

## 与 Screen/Depth 的关键差异

| 维度 | Screen / Depth | Portfolio |
|------|---------------|-----------|
| 核心问题 | "谁值得看？" / "好不好？" | "放在一起会怎样？" |
| 核心工作 | 定性 + 定量混合 | AI 横评 + 轻量计算 |
| Python 脚本占比 | 20-40% | ~10%（2-3 个脚本） |
| AI spawn 数 | 10-30 个 | ~3 个 |
| 人类介入点 | 0-2 个 | 1 个（启动时 Q1-Q4） |

Architecture philosophy: 方法论 23 章全是判断框架/评分卡/红旗检测——没有一章需要 Monte Carlo。架构匹配方法论本质，AI 做判断，Python 只做数据拉取和简单计算。

## 权重框架

### Strategic Weight（战略权重）— 长期持有基准

一条方程，三个输入，零隐藏参数：

```
w_i = mcap_i + (市值排名_i - VOH排名_i) × σ_mcap
```

- 市值权重 = 起点（市场在哪），VOH 排名 = 方向（谁更好）
- 排名差 × σ_mcap = 偏离幅度，数据自然决定步长
- 后处理：负数 clip → STRONG_SELL=0 → SELL≤3% → 上限裁剪 → 归一化

表达"长期相信谁"，季度/年度再平衡参考。

### Tactical Weights（战术权重）— 短期入场方案

表达"现在怎么买"：

| 版本 | 选股 | 加权 |
|------|------|------|
| 低 Beta 防御 | beta < 1 + 高 integrity | 1/vol 或 VOH 下调高 beta |
| 高 Beta 进攻 | beta > 1 | VOH 加权 + 放宽上限 |
| 等权 | 全量 | 1/N |
| 分红导向 | dividend top + CDP < 40% | 分红得分加权 |

计算量：排序 + 筛选 + 加权。不需要优化求解。

## 方法论的嵌入：Curiosity Checklist

方法论不是被动参考文档，而是蒸馏为一组探测性问题，AI 用它审讯组合方案：

- **预设 5-10 条**: 从方法论蒸馏，保证底线覆盖
- **自发 5-10 条**: AI 读 narrative 时触发
- 共 10-20 条，逐条排雷和找金子

## Pipeline 结构 (4 层)

```
Layer 0 — 数据摄入 (main session, 1 Python)
  → 读取 depth final_output.json + 拉 2 年日线 + 算 beta/corr/vol

Layer 1 — 宏观 + 横评 (1-3 AI spawn, sessions_spawn / Agent)
  → Curiosity Checklist 横评 → 排雷 + 找金子 → strategic_weights.json

Layer 2 — 战术变体 (main session, 1 Python)
  → 基于 strategic weights + beta/vol → tactical_weights.json (3-4 版本)

Layer 3 — 报告 (1 AI spawn, sessions_spawn / Agent)
  → portfolio_report.md + final_output.json
```

## 外部文档（权威来源）

所有业务需求和架构设计文档存放在平行文件夹：

- **BRD**: `/Users/wyhuang/docs/skillDev/hbs-bank/hbs-bank-portfolio/BRD.md`
- **架构**: `/Users/wyhuang/docs/skillDev/hbs-bank/hbs-bank-portfolio/ARCHITECTURE.md`
- **方法论**: `/Users/wyhuang/randomNoWalk/RBM-BNK-2026-003-银行业投研方法论-v0.3.md`

开发讨论、计划、架构决策也写入平行文件夹，不在项目内创建 docs/。

## 关键设计决策

1. **一条方程**: w = mcap + 排名差 × σ_mcap，无 α、无调和排名、无隐藏旋钮
2. **两层权重**: Strategic (长期) + Tactical (短期)，概念分离
3. **AI 横评是核心**: 12 家体检报告交叉比较，Checklist 驱动排名调整
4. **Curiosity Checklist**: 预设 + 自发，每道题输出排名/分组/散点，不做单家审计
5. **情景推演替代回测**: AI 基于 narrative + 知识推理，不做 Monte Carlo
6. **STRONG_SELL 排除**: weight = 0；SELL 最低配 (≤3%)
7. **不做逐家重新审计**: 回查 narrative 是例外验证，不是流程

## 用户交互

启动时一次 Q1-Q4，之后全自动运行：

- Q1: 投资目标（高 Beta / 低 Beta / 分红 / 均衡）
- Q2: 组合约束（规模 + 单只上限）
- Q3: 投资期限
- Q4: 特殊偏好（可选）

## 数据流

```
输入: depth final_output.json + 2 年日线(东方财富/akshare) + 中证银行指数
中间: portfolio_input.json → strategic_weights.json → tactical_weights.json
输出: portfolio_report.md + final_output.json
```

## 文件结构

```
hbs-bank-portfolio/
├── SKILL.md                       # Skill 入口 / main session 调度器 (OpenClaw 主格式)
├── CLAUDE.md                      # 本文件 (Claude Code 适配)
├── README.md                      # 人类可读概述
├── LICENSE                        # Apache 2.0
├── SETUP.md                       # 环境配置 + 平台适配指南
├── PLATFORMS.md                   # 平台兼容性说明
├── prompts/
│   ├── layer1_macro_cross.md      # L1: 宏观 + 横评 + 战略权重
│   └── layer3_report.md           # L3: 组合报告生成
├── scripts/
│   ├── env_scan.py                # 数据源检测
│   ├── fetch_market_data.py       # 拉价格 + 市值 + 指数
│   └── compute_tactical.py        # 战术变体生成
├── references/
│   ├── curiosity_checklist.md     # 预设好奇心问题清单（方法论蒸馏）
│   ├── voh_framework.md           # VOH 子维度 + 策略版本偏好映射
│   └── scenario_framework.md      # 情景推演指南
├── assets/
│   ├── output_schema.json
│   └── report_template.md
└── tests/
```

## 编码规范

- Python 脚本使用标准库 + numpy/pandas，避免小众依赖
- 计算逻辑：排序 + 筛选 + 加权，不做优化求解
- 所有脚本独立可运行，通过 JSON 文件松耦合
- 错误处理：计算失败时优雅降级（如可选标的不足 → 标注警告）

## Depth 接口约定

Portfolio 需要 Depth 提供：
- 完整 narrative + 结构化摘要 (~200 tokens/银行)
- VOH 子项 + 五级评级 + integrity/resilience 得分
- 建议: 业务类型（零售/对公/综合）、地域特征、NIM 敏感度

## OpenClaw 开发约定

- `SKILL.md` 为 OpenClaw 主格式，所有工具名使用 OpenClaw 原生名称
- Frontmatter 使用 `metadata.openclaw.allowed-tools` 声明所需工具
- Subagent 调度使用 `sessions_spawn`，支持并行执行
- `CLAUDE.md` 仅为 Claude Code 平台提供适配参考，不作为权威来源
