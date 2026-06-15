# Data Provider Architecture (设计稿)

## 动机

### 当前风险
- Eastmoney F10 API 无文档 / 无 SLA / 无版本号，字段名或 JSON 结构随时可能静默变更
- 腾讯行情 API 返回古老格式，解析脆弱
- 单数据源 = 单点故障，无 fallback 机制

### 开源诉求
- 其他用户应可通过自身配置获得更稳定/高质量的数据（如付费 Tushare）
- 社区开发者应在 Screen 和 Depth 阶段注入自定义数据维度（如 ESG 评分、管理层指标等）
- 所有扩展不应要求 fork 主仓库或修改管线核心逻辑

## 架构设计

参考 Issue 样式：Provider 抽象层，标准化字段注册表，可选的 DataProvider 链，自定义维度注入。

### Provider 抽象接口

```python
# scripts/providers/base.py
class DataProvider(ABC):
    @property
    def name(self) -> str: ...

    def fetch_bank_list(self) -> pd.DataFrame:
        """columns: code, name, type"""

    def fetch_financials(self, banks: list[str],
                         report_type: str) -> pd.DataFrame:
        """返回标准化字段的截面财务数据"""

    def fetch_valuation(self, banks: list[str]) -> pd.DataFrame:
        """返回 PE / PB / 市值 等估值数据"""

    def fetch_financials_multi_period(self, banks: list[str],
                                      periods: int) -> pd.DataFrame:
        """可选：多期数据，用于 D4 成长性计算"""

    def is_available(self) -> bool:
        """检查 provider 是否可用（token 有效等）"""
```

### 标准化字段注册表

```yaml
# references/canonical_fields.yaml
fields:
  CET1:
    type: float
    unit: "%"
    description: 核心一级资本充足率
    mappings:
      eastmoney: HXYJBCZL
      tushare: cet1_ratio
  NPL_RATIO:
    type: float
    unit: "%"
    description: 不良贷款率
    mappings:
      eastmoney: NONPERLOAN
      tushare: npl_ratio
  ROE:
    type: float
    unit: "%"
    description: 净资产收益率
    mappings:
      eastmoney: ROEJQ
      tushare: roe
  # ... 其余字段类似
```

作用：`generate_bank_cards.py` 和所有评分逻辑只认 `CET1`、`NPL_RATIO` 等标准化名称，不感知底层来源。

### Provider 配置

```yaml
# data/config.yaml (可选，不存在则全默认走 Eastmoney)
data_providers:
  primary:
    name: tushare
    token: ${TUSHARE_TOKEN}
    params:
      timeout: 30
  fallback:
    name: eastmoney

custom_dimensions:
  - id: D6_ESG
    name: ESG 评分
    weight: 0.10
    source:
      type: csv
      path: data/custom/esg_scores.csv
      key_column: bank_code
      value_column: esg_score
  - id: F12_green_loan
    name: 绿色信贷占比
    source: ...
```

### 统一数据获取入口

```python
# scripts/fetch_data.py
# 1. 读取 config（可选）
# 2. 按 primary → fallback 顺序尝试 fetch
# 3. Provider 超时/报错 → 自动切 fallback
# 4. 合并自定义维度（custom_dimensions）
# 5. 输出标准化 raw_data.parquet / csv
```

### 自定义维度注入点

custom_dimensions 中的数据会在以下位置出现：
- `index.csv` 中作为额外列
- 银行卡片 `cards/*.md` 中作为额外字段 / Curiosity Flags
- 各层 AI 派生 prompt 中可选引用
- `scoring_rules.md` 中可声明是否纳入总分以及权重

## 改动清单

| 文件 | 改动性质 | 说明 |
|------|---------|------|
| `references/canonical_fields.yaml` | **新建** | 标准化字段注册表 |
| `references/field_mapping.md` | 保留或并入 | 过渡期可保留，后续废弃 |
| `scripts/providers/base.py` | **新建** | Provider ABC |
| `scripts/providers/eastmoney.py` | **新建** | 从 `fetch_financials.py` + `pb_fetcher.py` 提取 |
| `scripts/providers/tushare.py` | **新建** | Tushare 实现（社区贡献 / 可选） |
| `scripts/fetch_data.py` | **新建** | 统一数据获取入口 |
| `scripts/fetch_financials.py` | 保留 | 降级为 Eastmoney Provider 的实现细节 |
| `scripts/pb_fetcher.py` | 保留 | 同上 |
| `scripts/generate_bank_cards.py` | 小改 | 适配标准化列名 |
| `data/config.yaml` | **新建** | Provider 配置模板 |
| `SKILL.md` | 小改 | L0 数据工程步骤更新 |
| `prompts/*` | 不改 | AI 派生不感知数据来源变动 |

## 分阶段实施建议

- **Phase 0**：`canonical_fields.yaml` + Provider 抽象层。纯重构，不改变现有行为，但为后续铺路。
- **Phase 1**：Eastmoney + Tushare Provider 实现。社区用户配置 token 即可切源。
- **Phase 2**：自定义维度注册机制。社区开发者可注入 csv/excel 数据，不 fork 仓库。
- **Phase 3**：Depth 阶段 plugin 机制。社区贡献特定分析模块。

## 说明

- 默认（无 config 文件）行为完全不变，保持开箱即用的免费路径
- Provider 链确保稳定：primary 挂了自动 fallback，不影响管线运行
- 所有新文件放在现有目录结构内，不引入新依赖
