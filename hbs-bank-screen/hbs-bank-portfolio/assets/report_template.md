# HBS 银行组合报告

**生成日期**: {{RUN_DATE}}
**投资目标**: {{INVESTMENT_OBJECTIVE}}
**组合约束**: {{PORTFOLIO_SIZE}} 只, 单只上限 {{SINGLE_STOCK_CAP}}%
**投资期限**: {{HORIZON}}
**数据基准日**: {{DATA_DATE}}
**Depth 数据源**: {{DEPTH_SOURCE}}

---

## 一、宏观环境判断

### 利率方向
{{RATE_OUTLOOK}}

### 信用周期
{{CREDIT_CYCLE}}

### 监管姿态
{{REGULATORY_POSTURE}}

### 关键风险因素
{{KEY_RISK_FACTORS}}

---

## 二、横评发现

### 2.1 排雷清单 (Mine-Sweeping)

| # | 风险信号 | 涉及银行 | 严重度 | 权重影响 |
|---|---------|---------|--------|---------|
{{MINE_SWEEPING_ROWS}}

### 2.2 找金子清单 (Gold-Finding)

| # | 金子信号 | 涉及银行 | 置信度 | 权重影响 |
|---|---------|---------|--------|---------|
{{GOLD_FINDING_ROWS}}

### 2.3 Curiosity Checklist 执行摘要

- Phase 1 宏观校准: {{PHASE1_COUNT}}/3 条
- Phase 2 排名与异常值: {{PHASE2_COUNT}}/10 条触发
- Phase 3 压力测试: 4/4 条
- AI 自发问题: {{SPONTANEOUS_COUNT}} 条
- **排雷信号**: {{MINE_COUNT}} | **找金子信号**: {{GOLD_COUNT}}

### 2.4 VOH 排名调整摘要

| 银行 | Depth排名 | Portfolio排名 | 调整 | 核心理由 |
|------|----------|--------------|------|---------|
{{VOH_RANK_ADJUSTMENT_ROWS}}

---

## 三、战略权重（长期持有基准）

| 排名 | 银行 | 代码 | 评级 | 市值权重 | VOH排名 | 战略权重 | 调仓方向 |
|------|------|------|------|---------|--------|---------|---------|
{{STRATEGIC_WEIGHT_ROWS}}

**权重公式**: w = mcap + (市值排名 - VOH排名) x sigma_mcap
**sigma_mcap**: {{SIGMA_MCAP}}

**排除**: {{EXCLUDED_BANKS}}

---

## 四、战术权重（短期入场方案）

### 版本 A: 低 Beta 防御
{{LOW_BETA_DEFENSIVE_TABLE}}

组合 Beta: {{LOW_BETA_PORTFOLIO_BETA}} | 组合 Vol: {{LOW_BETA_PORTFOLIO_VOL}}

### 版本 B: 高 Beta 进攻
{{HIGH_BETA_AGGRESSIVE_TABLE}}

组合 Beta: {{HIGH_BETA_PORTFOLIO_BETA}} | 组合 Vol: {{HIGH_BETA_PORTFOLIO_VOL}}

### 版本 C: 等权
{{EQUAL_WEIGHT_TABLE}}

组合 Beta: {{EQUAL_WEIGHT_PORTFOLIO_BETA}} | 组合 Vol: {{EQUAL_WEIGHT_PORTFOLIO_VOL}}

### 版本 D: 分红导向
{{DIVIDEND_ORIENTED_TABLE}}

组合 Beta: {{DIVIDEND_PORTFOLIO_BETA}} | 组合 Vol: {{DIVIDEND_PORTFOLIO_VOL}}

---

## 五、情景压力测试

### 利率 +100bp
{{RATE_SHOCK_RESULTS}}

### 信用冲击 +200bp NPL
{{CREDIT_SHOCK_RESULTS}}

### 隐性同源风险
{{COMMON_RISK_FACTORS}}

### 业务与地域覆盖
{{BUSINESS_REGIONAL_COVERAGE}}

---

## 六、组合风险提示

1. **集中度风险**: {{CONCENTRATION_RISK}}
2. **宏观敏感度**: {{MACRO_SENSITIVITY}}
3. **评级风险**: {{RATING_RISK}}
4. **流动性风险**: {{LIQUIDITY_RISK}}
{{ADDITIONAL_RISK_WARNINGS}}

---

*本报告由 HBS-Bank-Portfolio 自动生成。仅供参考研究，不构成投资建议。*
*权重公式: w = mcap + 排名差 x sigma_mcap，一条方程，三个输入，零隐藏参数。*
