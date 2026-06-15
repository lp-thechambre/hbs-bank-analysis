# Mosaic Search Guide — Edge Signal Search Strategy

This document provides the search source catalog, query templates, and confidence framework for Layer 2 edge signal searches.

## Search Source Catalog

### 1. Employee Signals

| Platform | URL Pattern | Search Query Template | Signal Types |
|----------|------------|----------------------|--------------|
| 脉脉 (Maimai) | maimai.cn | `{bank_name} 裁员` `{bank_name} 工资` `{bank_name} 部门` | Layoffs, salary delays, restructuring, management complaints |
| 知乎 (Zhihu) | zhihu.com | `在{bank_name}工作` `{bank_name} 待遇` | Employee experience, culture, management quality |
| 微博 (Weibo) | weibo.com | `{bank_name} 员工` `{bank_name} 维权` | Public employee complaints, labor disputes |

**Reliability**: Low-Medium. Self-reported, biased toward negative experiences. Corroborate across 2+ independent sources.

### 2. Hiring Signals

| Platform | URL Pattern | Search Query Template | Signal Types |
|----------|------------|----------------------|--------------|
| Boss直聘 | zhipin.com | `{bank_name}` | Job posting volume, position types, salary ranges |
| 51job | 51job.com | `{bank_name}` | Mass hiring campaigns, department-specific hiring |
| 猎聘 (Liepin) | liepin.com | `{bank_name}` | Senior/key position hiring, executive recruitment |
| 银行招聘网 | yinhangzhaopin.com | `{bank_name} 招聘` | Official recruitment announcements |

**Signal Interpretation**:
- Large-scale customer manager hiring → business expansion OR high turnover replacement
- Risk management / NPL specialist hiring surge → asset quality problems being addressed
- IT / data roles hiring surge → digital transformation investment
- Hiring freeze or dramatic reduction → cost cutting or business contraction

**Reliability**: Medium. Observable behavior, less subject to spin than employee posts.

### 3. Regulatory Actions

| Platform | URL Pattern | Search Query Template | Signal Types |
|----------|------------|----------------------|--------------|
| 银保监会 (CBIRC) | cbirc.gov.cn | `{bank_name} 处罚` `{bank_name} 罚款` | Fines, regulatory actions, business restrictions |
| 央行 (PBoC) | pbc.gov.cn | `{bank_name} 行政处罚` | AML penalties, regulatory violations |
| 证监会 (CSRC) | csrc.gov.cn | `{bank_name} 监管` | Securities-related actions (for listed banks) |
| 交易所 (SSE/SZSE) | sse.com.cn / szse.cn | `{bank_code}` | Exchange inquiries, delisting warnings |

**Reliability**: High. Official records with specific violations and amounts.

**Key Search Terms**:
- `罚单` (fine notice)
- `行政处罚` (administrative penalty)
- `监管谈话` (regulatory interview)
- `责令改正` (ordered rectification)
- `业务限制` (business restriction)

### 4. Industry Media & Rumors

| Platform | URL Pattern | Search Query Template | Signal Types |
|----------|------------|----------------------|--------------|
| 财联社 (CLS) | cls.cn | `{bank_name}` | Breaking news, industry reports |
| 华尔街见闻 | wallstreetcn.com | `{bank_name}` | Market-moving news, analysis |
| 东方财富 (Eastmoney) | eastmoney.com | `{bank_code}` | Stock forum discussions, news |
| 雪球 (Xueqiu) | xueqiu.com | `$ {bank_code}` `{bank_name} 分析` | Investor analysis, rumor discussions |
| 21世纪经济报道 | 21jingji.com | `{bank_name}` | In-depth financial journalism |

**Reliability**: Low-Medium. Distinguish between: official news (medium-high reliability), analyst reports (medium), forum posts (low). Xueqiu long-form analysis by known authors can be high quality.

### 5. Supply Chain & Related Entities

| Platform | URL Pattern | Search Query Template | Signal Types |
|----------|------------|----------------------|--------------|
| 企业预警通 | qyyjt.cn | `{bank_name}` | Risk alerts, negative news aggregation |
| 天眼查 | tianyancha.com | `{bank_name}` | Legal cases, equity changes, related companies |
| 企查查 | qichacha.com | `{bank_name}` | Shareholder changes, judicial risks |
| 中国裁判文书网 | wenshu.court.gov.cn | `{bank_name}` | Lawsuits, judgments, enforcement actions |

**Reliability**: Medium-High. Legal and administrative records are official. Risk alert aggregators are medium reliability.

### 6. Procurement & Bidding

| Platform | URL Pattern | Search Query Template | Signal Types |
|----------|------------|----------------------|--------------|
| 中国政府采购网 | ccgp.gov.cn | `{bank_name} 采购` | IT system procurement, service contracts |
| 招标网 | bidcenter.com.cn | `{bank_name} 招标` | Major project bidding, vendor selection |
| 企查查 (bidding) | qichacha.com | `{bank_name} 中标` | Contracts won, bidding patterns |

**Signal Interpretation**:
- Core banking system replacement tender → major IT investment
- Security/risk system procurement surge → regulatory compliance push
- Procurement budget cut → cost reduction
- Vendor change from foreign to domestic → tech sovereignty shift

**Reliability**: Medium. Public procurement records are official but may not capture all spending.

### 7. Capital Flow & Debt Markets

| Platform | URL Pattern | Search Query Template | Signal Types |
|----------|------------|----------------------|--------------|
| 中国货币网 | chinamoney.com.cn | `{bank_name} 同业存单` | NCD issuance rate, volume changes |
| 上清所 | shclearing.com.cn | `{bank_name} 债券` | Bond issuance, maturity schedule |
| 企业预警通 | qyyjt.cn | `{bank_name} 债务` | Debt maturity walls, refinancing risk |

**Signal Interpretation**:
- NCD issuance rate > peer average + 50bp → funding stress
- Bond issuance volume surging → aggressive balance sheet expansion OR liquidity gap filling
- Concentrated debt maturity → refinancing risk
- Shift from NCD to longer-term bonds → improving liability structure

**Reliability**: Medium-High. Financial market data is official and real-time.

### 8. Physical Operations & Branch Network

| Platform | URL Pattern | Search Query Template | Signal Types |
|----------|------------|----------------------|--------------|
| 金融监管总局 | nfra.gov.cn | `{bank_name} 网点` `{bank_name} 支行` | Branch approvals, closures |
| 银行官网 | {bank}.com | 网点查询 | Branch count changes, service area shifts |

**Signal Interpretation**:
- Rural/suburban branch expansion → inclusive finance push, regulatory compliance
- Urban branch consolidation → cost optimization, digital shift
- Branch closures in specific region → regional strategy retreat
- New specialty branches (tech/ green finance) → strategic focus areas

**Reliability**: Medium-High. Branch changes require regulatory approval and are publicly filed.

---

## Search Strategy

### Query Formulation

**Basic pattern**: `{bank_name_short} {signal_keyword}`

Examples:
- `招商银行 裁员`
- `招商 对公 业务 收缩`
- `600036 处罚`
- `招行 房地产 不良`

**Time-bounded** (when recency matters):
- `招商银行 2025 处罚`
- `招商银行 2025 监管`

**Competitor cross-reference** (detect sector-wide vs bank-specific):
- `银行 对公业务 收缩 2025`
- `股份制银行 薪酬 调整`

### Search Priority

1. **High Priority** (search first):
   - Regulatory actions (official, high reliability)
   - Supply chain signals for banks with L1 flags related to concentration risk
   - Employee signals for banks with L1 flags related to business contraction

2. **Medium Priority**:
   - Hiring signals for banks with L1 flags related to strategy changes
   - Industry media for banks with high-impact L1 flags

3. **Low Priority** (search only if budget remains):
   - Forum/community discussions (low signal-to-noise)
   - Generic news without specific claims

### Budget Allocation

With {edge_search_budget} total searches:
1. Reserve 2-3 searches per bank with `high` severity flags.
2. Reserve 1-2 searches per bank with `medium` severity flags.
3. Reserve 2-3 searches for cross-bank pattern detection (e.g., "银行业 不良贷款 认定 2025").
4. Keep 2-3 searches as buffer for unexpected leads.

---

## Confidence Framework

| Level | Criteria | Example |
|-------|----------|---------|
| `high` | Official source OR 2+ independent sources with consistent details | CBIRC fine notice with specific amount and violation; 2 news outlets reporting same management change |
| `medium` | Single credible source OR 1 source with partial corroboration | CLS article citing named sources; Maimai post with specific department and timeline |
| `low` | Single unverified source OR anonymous/hearsay | Anonymous Xueqiu post; Weibo post with vague claims |

---

## Output Guidance

For each search that produces a signal, record:

```json
{
  "code": "SH600036",
  "signal_type": "regulatory_action",
  "source_url": "https://www.cbirc.gov.cn/...",
  "source_type": "银保监会",
  "confidence": "high",
  "corroborates": ["L1_SH600036_003"],
  "contradicts": [],
  "summary": "2025年3月因理财业务违规被罚款120万元, 涉及理财产品销售适当性管理不到位"
}
```

For searches that produce NO signal (negative finding), record briefly:
```json
{
  "code": "SH600036",
  "signal_type": "workplace_rumor",
  "search_query": "招商银行 裁员 2025",
  "result": "no relevant signals found",
  "confidence": "low"
}
```

Negative findings are valuable — they tell L5 (Vice/Chief) that a potential concern was investigated and not found.

---

## Ethical & Legal Boundary

- Only search PUBLICLY available information. Do not attempt to access private databases, paywalled content, or restricted sites.
- Do not search for or record personal identifying information beyond what is publicly reported in official sources.
- Respect platform robots.txt and rate limits.
- The purpose is investment research signal detection, not corporate espionage.
