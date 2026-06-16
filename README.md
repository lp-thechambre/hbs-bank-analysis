# HBS-Bank-Analysis

> **Homebrew Strategy** — A-Share Bank Investment Research System
>
> 一个模块化的 AI 投研分析系统，覆盖银行股筛选 → 深度分析 → 组合构建全流程。

[English](README.en.md)

## 项目结构

```
hbs-bank-analysis/
├── hbs-bank-screen/        Layer 1: 初筛（42 → 10-15 家）
├── hbs-bank-depth/         Layer 2: 深度分析（完整审计）
├── hbs-bank-portfolio/     Layer 3: 组合构建（权重 + 横评）
├── hbs-bank-pdf-catcher/   增量技能：仅 PDF 下载（L0a-L0b）
└── hbs-bank-data-guy/      增量技能：仅数据结构化（L0c-L0e）
```

## 快速入口

| 你要做什么 | 对 AI 说 |
|-----------|---------|
| 跑初筛 | `screen banks` / `跑一下银行初筛` |
| 深度分析 | `run depth on 600036` / `深度分析 招商银行` |
| 组合构建 | `run portfolio on depth output` / `组合构建` |
| 只下载报表 | `run pdf-catcher on 600036` |
| 只结构化数据 | `run data-guy on {data_dir}` |

## 支持的 Agent 平台

| 平台 | 入口文件 | 状态 |
|------|---------|------|
| **OpenClaw** | `hbs-bank-*/skill-md for openclaw/SKILL.md` | 主开发平台 |
| **Claude Code** | `hbs-bank-*/skill-md for claude-code/SKILL.md` | 交互式运行适配版 |
| **KimiClaw / 其他 OpenClaw 衍生** | 理论上兼容 | 见「已知局限」 |

---

## 设计哲学

### 基础设施最低原则

这套系统在最低基础设施下设计：

- 不需要任何 API Key
- 不需要 GPU、不需要数据库
- Python 依赖仅：`requests`、`pdfplumber`、`numpy`、`pandas`

任何分析师都可以在本地跑通全流程。但如果你能接入更好的数据来源和工具链，管道质量会显著提升——例如专业金融数据库（Wind、Bloomberg、iFinD）、更专业的 PDF 解析服务、高质量的网络搜索后端等。架构通过文件契约解耦，升级数据源不需要改动分析逻辑。

### 文件即接口

每层间通信通过磁盘文件完成，每层输出都是可读的 JSON/Markdown，可以独立检验、手动替换、重跑。审计透明，每个数值都有 `data_provenance` 追踪。

### AI 判断 vs 脚本计算

Python 脚本只负责数据搬运和确定性计算；AI spawn 负责量化分析、定性判断、文本解读和综合评分。两者通过文件契约解耦。

---

## 已知局限

### 1. 模型依赖

分析质量取决于运行它的 AI 模型。不同模型表现差异很大：

| 模型/平台 | 初筛 | PDF 结构化 | 定量分析 | 定性分析 |
|-----------|------|-----------|---------|---------|
| **Claude Code + DeepSeek V4** | ✅ | ✅ | ✅ | ✅ |
| **OpenClaw (Claude backend)** | ✅ | ⚠️ 偶有格式漂移 | ✅ | ✅ |
| **KimiClaw / Kimi K2.x** | ✅ | ❌ 发散，会自行改数据 | ⚠️ 不可控 | ✅ 有惊喜 |

**实测感受**：Kimi 在需要精确执行固定步骤（如拉取指定 PDF、精确提取数值）时表现出明显的"过度思考"倾向——它会自发优化执行路径、重新设计方案。这在 L0 数据工程阶段是致命的，但在 L1-L5 金融分析阶段，这种发散有时能发现意外的信号。

建议：L0 数据准备阶段使用 pdfCatcher + dataGuy 独立执行或换用其他模型；L1-L5 分析推理阶段可以交给 Kimi。

### 2. 数据来源

当前使用 Cninfo（巨潮资讯网）和 Eastmoney（东方财富）公开 API。这些免费但：
- API 偶而不稳定或限流
- 部分 PDF 是扫描件，结构化提取困难
- Pillar 3 部分银行合并到年报中，非独立文件

### 3. Token 消耗

管道的 token 消耗主要来自各阶段工具调用的返回数据在对话历史中的累积。处理 10+ 家银行时，上下文可能在管道后半段显著膨胀。建议部署后先小规模测试观察 token 用量。

### 4. 批次限制

单次深度分析建议控制在 15 家以内。超过需分批执行或使用更经济的模型后端。

### 5. 不是投资建议

所有输出均为研究框架的分析结果，不构成投资建议。详见各技能目录下的 LICENSE。

---

## 开发路线

- [x] v0.3 — 三件套核心管道打通
- [x] 多平台适配（OpenClaw + Claude Code）
- [x] pdfCatcher + dataGuy 增量技能
- [ ] 更完善的 KPI 门控体系
- [ ] 专业数据源接入示例
- [ ] 回测与业绩跟踪模块

## 许可

Apache 2.0 — 详见各技能目录下的 [LICENSE](hbs-bank-depth/LICENSE)。

## 致谢

Built with Claude Code and DeepSeek V4 Pro.

---

*本 README 使用中文撰写，因为项目的主要用户群体是中文金融分析师。「Research Only, Not Advice.」*
