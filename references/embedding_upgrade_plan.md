# HBS-Screen Embedding 升级计划

> 版本: v0.1 | 日期: 2026-06-02 | 上游: Qwen3-Embedding-0.6B (本地 oMLX :8000)

---

## 概览

本机已部署 Qwen3-Embedding-0.6B 向量模型，通过 oMLX 的 `/v1/embeddings` 端点提供服务。OpenClaw memory_search 已完成对接。以下是将 Embedding 技术融入 HBS-Screen 的四个方向。

---

## 方向一：参考文档 RAG（推荐优先实施）

### 现状痛点

每个 Phase spawn 的 prompt 中需要嵌入：
- `references/scoring_rules.md` 全量内容
- `references/field_mapping.md` 全量内容
- `references/methodology.md` 全量内容
- 部分 `references/bank_list.md`

导致：prompt 臃肿、token 浪费、规则改一处需要改所有 spawn 的 prompt 模板。

### 改造方案

```
before:
  Scheduler Spawn Prompt = 规则全文 + 银行数据 + 分析指令
                                 ↑ 硬编码，改规则得改代码

after:
  references/ → 分段 → 向量化 → 存入 OpenClaw memory 索引
  
  Phase spawn 运行时：tools.allow: [memory_search]
  spawn prompt 中只写：
    "规则在 memory 中，搜索 'scoring_rules/phase1' 获取"
  
  需要 memory_search 时：
    memory_search("phase1 quantitative thresholds PB ROE")
    → 精准召回相关规则段落
```

### 具体操作

1. **分拆 reference 文档**
   将 `scoring_rules.md`、`field_mapping.md`、`methodology.md` 按小节拆成独立段落文件，存入 `references/chunks/` 目录

2. **建立向量索引**
   通过 OpenClaw 的 memory index 自动抓取 `references/chunks/` 下的内容并向量化

3. **修改 spawn prompt**
   每个 Phase spawn 的 `allowed-tools` 中加入 `memory_search`
   不再硬塞规则全文，改为 spawn 自主按需检索

### 收益

| 指标 | 改善 |
|------|------|
| 每个 spawn 的 prompt 大小 | 减少 40-60% |
| 规则修改响应时间 | 改 .md 即可，无需改代码 |
| 多 Phase 一致性 | 所有 Phase 读同一份向量化规则，避免漂移 |

---

## 方向二：历史筛选举证

### 现状痛点

每次 screening 结果写入 `results/final_output.json`，但历史结果不能语义检索。下次聊到某家银行时，无法召回之前对该行的分析结论。

### 改造方案

每次 screening 完成后，将 `final_output.json` 的内容写入 OpenClaw memory，供后续检索。

```
screening 完成
  → 解析 final_output.json
  → 写入 memory/bank-screen/YYYY-MM-DD.md
  → Qwen3-Embedding 自动索引

下次用户问：
  "上次 PB < 0.6 的银行有哪些？"
  → memory_search("PB less than 0.6 screening")
  → 命中历史结果
  → 秒回
```

### 收益

- 从「每次都从零开始」变成「可以基于历史讨论」
- 对同一家银行做纵向比较（本期 vs 上期指标变化）

---

## 方向三：银行相似度搜索

### 场景

用户说：
> "找一家跟招商银行资产质量类似的城商行"

传统做法：硬编码维度对比。
Embedding 做法：将各家银行的财务特征向量化，做向量相似度匹配。

### 改造方案

```python
# 伪代码
banks = load_all_banks_financials()
for bank in banks:
    text = format_bank_profile(bank)  # "PB:0.58 ROE:11.2 NPL:1.25 CAR:13.5 ..."
    embedding = embed(text)  # Qwen3-Embedding 生成向量
    store(bank.code, embedding)

query = "PB低、ROE稳定、资产质量向好的城商行"
query_vec = embed(query)
results = vector_search(query_vec, top_k=5)
# → 返回最相似的前5家银行
```

### 收益

- 自然语言查询银行：不再需要结构化筛选条件
- 发现分析师可能忽略的相似性

---

## 方向四：Phase 3 好奇心检测升级

### 现状

Phase 3 的「好奇心审查」依赖硬编码的触发规则（如：PB < 0.5 且 ROE > 10% 但 NPL 上升）。这些规则可能遗漏异常模式。

### 改造方案

```
42 家银行的财务数据 → 向量化 → 聚类分析
                                  ↓
偏离聚类中心的银行 → 自动标记为 "模式异常" → 送入 Phase 3
```

即：**无监督异常检测取代硬编码规则**。

需要额外工具：`sklearn`（DBSCAN / Isolation Forest），但数据流程与现有 script 兼容。

### 收益

- 发现规则遗漏的异常银行
- 随着新银行上市/退市自动适应
- 分析师查看 flagged 银行时更有的放矢

---

## 实施优先级

| 优先级 | 方向 | 预估工时 | 依赖 |
|--------|------|----------|------|
| P0 | 方向一：参考文档 RAG | 2-3h | 现有 infrastructure 就绪 |
| P1 | 方向二：历史筛选举证 | 1-2h | 方向一完成后的自然延伸 |
| P2 | 方向四：Phase 3 异常检测 | 3-5h | 需要 sklearn |
| P3 | 方向三：银行相似度搜索 | 2-3h | 需要额外的向量存储 |

---

## 技术前提

- ✅ Qwen3-Embedding-0.6B 已部署在 `http://localhost:8000/v1`
- ✅ OpenClaw memory_search 已对接本地 embedding
- ❌ 尚无专门的向量数据库（当前用 OpenClaw 内置 SQLite 索引，够用）
- ❌ references/ 尚未分拆为独立段落
