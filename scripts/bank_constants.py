"""
Shared constants for HBS-Screen v1 (ARCHITECTURE-v1).

Optional reference module. The primary pipeline uses web_fetch + AI spawns.
These constants are provided for offline/Python-based use and as a reference
for bank codes, thresholds, and scoring weights.
"""

# ============================================================
# API Configuration (from fetch_financials.py)
# ============================================================

API_BASE = "https://datacenter.eastmoney.com/api/data/v1/get"
QUOTE_API = "https://push2.eastmoney.com/api/stock/get"
BANK_FILTER = '(SECURITY_TYPE_CODE="058001001")(ORG_TYPE="银行")'
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 4, 8]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://data.eastmoney.com/",
}

QUOTE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://quote.eastmoney.com/",
}

# ============================================================
# API Column Definitions (from fetch_financials.py)
# ============================================================

MAIN_FINANCIAL_COLUMNS = [
    "SECUCODE", "SECURITY_NAME_ABBR", "REPORT_DATE",
    "HXYJBCZL",               # CET1
    "NONPERLOAN",             # NPL ratio
    "NON_PERFORMING_LOAN",    # NPL balance
    "ROEJQ",                  # ROE (annualized quarterly)
    "BLDKBBL",                # PCR
    "TOTAL_ASSETS_PK",        # Total assets
    "BPS",                    # Book value per share
    "EPSJB",                  # Basic EPS
    "PARENTNETPROFIT",        # Net profit attributable to parent
    "GROSSLOANS",             # Gross loans
    "LOAN_PROVISION_RATIO",   # Loan provision ratio
    "REVENUE_RATIO",          # Cost-income ratio
    "NET_INTEREST_MARGIN",    # NIM
    "NEWCAPITALADER",         # Total CAR
    "FIRST_ADEQUACY_RATIO",   # Tier 1 CAR
]

PROFIT_STATEMENT_COLUMNS = [
    "SECUCODE", "SECURITY_NAME_ABBR", "REPORT_DATE",
    "TOTAL_OPERATE_INCOME",
    "OPERATE_INCOME",
    "NET_INTEREST_INCOME",
    "COMMISSION_INCOME",
]

DIVIDEND_COLUMNS = [
    "SECUCODE", "SECURITY_NAME_ABBR", "REPORT_DATE",
    "CASH_DIVIDEND_PER_SHARE",
    "DIVIDEND_RATIO",
]

# ============================================================
# Phase 1 Thresholds (from compute_scores.py)
# ============================================================

CET1_MIN = 8.5          # Regulatory floor (7.5% + 1% buffer)
NPL_MAX = 3.0           # Industry mean ~1.6% + 2σ
PCR_MIN = 120.0         # Regulatory minimum since 2020
CRITICAL_FIELDS = {"HXYJBCZL", "NONPERLOAN", "ROEJQ", "BLDKBBL", "BPS", "TOTAL_ASSETS_PK"}
MAX_MISSING_CRITICAL = 3

# ============================================================
# Bank Type Overrides (from compute_scores.py + bank_list.md)
# ============================================================

TYPE_OVERRIDES = {
    # Large state-owned (6)
    "SH601398": "traditional_commercial",  # 工商银行
    "SH601939": "traditional_commercial",  # 建设银行
    "SH601288": "traditional_commercial",  # 农业银行
    "SH601988": "traditional_commercial",  # 中国银行
    "SH601328": "traditional_commercial",  # 交通银行
    "SH601658": "traditional_commercial",  # 邮储银行
    # Joint-stock (integrated)
    "SH600036": "integrated",              # 招商银行
    "SH601166": "integrated",              # 兴业银行
    "SZ000001": "integrated",              # 平安银行
}

# ============================================================
# 42 Bank Master List (from references/bank_list.md)
# ============================================================

BANK_LIST = [
    # Large state-owned (6)
    {"code": "SH601398", "name": "工商银行", "group": "large_state_owned"},
    {"code": "SH601939", "name": "建设银行", "group": "large_state_owned"},
    {"code": "SH601288", "name": "农业银行", "group": "large_state_owned"},
    {"code": "SH601988", "name": "中国银行", "group": "large_state_owned"},
    {"code": "SH601328", "name": "交通银行", "group": "large_state_owned"},
    {"code": "SH601658", "name": "邮储银行", "group": "large_state_owned"},
    # Joint-stock (9)
    {"code": "SH600036", "name": "招商银行", "group": "joint_stock"},
    {"code": "SH601166", "name": "兴业银行", "group": "joint_stock"},
    {"code": "SH600016", "name": "民生银行", "group": "joint_stock"},
    {"code": "SH600000", "name": "浦发银行", "group": "joint_stock"},
    {"code": "SH601818", "name": "光大银行", "group": "joint_stock"},
    {"code": "SH600015", "name": "华夏银行", "group": "joint_stock"},
    {"code": "SZ000001", "name": "平安银行", "group": "joint_stock"},
    {"code": "SH601998", "name": "中信银行", "group": "joint_stock"},
    {"code": "SH601916", "name": "浙商银行", "group": "joint_stock"},
    # City commercial (17)
    {"code": "SZ002142", "name": "宁波银行", "group": "city_commercial"},
    {"code": "SH601009", "name": "南京银行", "group": "city_commercial"},
    {"code": "SH601229", "name": "上海银行", "group": "city_commercial"},
    {"code": "SH600926", "name": "杭州银行", "group": "city_commercial"},
    {"code": "SH601838", "name": "成都银行", "group": "city_commercial"},
    {"code": "SH601997", "name": "贵阳银行", "group": "city_commercial"},
    {"code": "SH601169", "name": "北京银行", "group": "city_commercial"},
    {"code": "SH601577", "name": "长沙银行", "group": "city_commercial"},
    {"code": "SH601963", "name": "重庆银行", "group": "city_commercial"},
    {"code": "SH601528", "name": "瑞丰银行", "group": "city_commercial"},
    {"code": "SH601860", "name": "紫金银行", "group": "city_commercial"},
    {"code": "SH601187", "name": "厦门银行", "group": "city_commercial"},
    {"code": "SH601825", "name": "沪农商行", "group": "city_commercial"},
    {"code": "SH601665", "name": "齐鲁银行", "group": "city_commercial"},
    {"code": "SH601128", "name": "常熟银行", "group": "city_commercial"},
    {"code": "SH601077", "name": "渝农商行", "group": "city_commercial"},
    {"code": "SH600908", "name": "无锡银行", "group": "city_commercial"},
    # Rural commercial (10)
    {"code": "SH603323", "name": "苏农银行", "group": "rural_commercial"},
    {"code": "SZ002839", "name": "张家港行", "group": "rural_commercial"},
    {"code": "SZ002807", "name": "江阴银行", "group": "rural_commercial"},
    {"code": "SZ002958", "name": "青农商行", "group": "rural_commercial"},
    {"code": "SH600928", "name": "西安银行", "group": "rural_commercial"},
    {"code": "SH600919", "name": "江苏银行", "group": "rural_commercial"},
    {"code": "SZ002936", "name": "郑州银行", "group": "rural_commercial"},
    {"code": "SZ002948", "name": "青岛银行", "group": "rural_commercial"},
    {"code": "SZ001227", "name": "兰州银行", "group": "rural_commercial"},
    {"code": "SZ002966", "name": "苏州银行", "group": "rural_commercial"},
]

# Derive ordered code list
BANK_CODES = [b["code"] for b in BANK_LIST]
BANK_NAMES = {b["code"]: b["name"] for b in BANK_LIST}
BANK_GROUPS = {b["code"]: b["group"] for b in BANK_LIST}

# ============================================================
# Scoring Weights (from compute_scores.py)
# ============================================================

# Dimension weights for composite score
DIMENSION_WEIGHTS = {
    "D1_capital_preservation": 0.25,
    "D2_asset_quality": 0.25,
    "D3_profitability": 0.20,
    "D4_growth": 0.15,
    "D5_valuation": 0.15,
}

# D1 sub-indicator weights
D1_SUB_WEIGHTS = {"HXYJBCZL": 0.60, "NEWCAPITALADER": 0.25, "FIRST_ADEQUACY_RATIO": 0.15}

# D2 sub-indicator weights
D2_SUB_WEIGHTS = {"NONPERLOAN": 0.55, "BLDKBBL": 0.30, "LOAN_PROVISION_RATIO": 0.15}

# D3 sub-indicator weights by bank type
D3_SUB_WEIGHTS = {
    "traditional_commercial": {"ROEJQ": 0.40, "RORWA": 0.30, "NET_INTEREST_MARGIN": 0.20, "non_interest": 0.10},
    "integrated": {"ROEJQ": 0.35, "RORWA": 0.25, "NET_INTEREST_MARGIN": 0.15, "non_interest": 0.25},
    "trading_ib": {"ROEJQ": 0.30, "RORWA": 0.20, "NET_INTEREST_MARGIN": 0.00, "non_interest": 0.50},
}

# D5 sub-indicator weights
D5_SUB_WEIGHTS = {"PB": 0.50, "DPR": 0.30, "EPS_YIELD": 0.20}

# ============================================================
# Curiosity Flag Definitions (from compute_scores.py)
# ============================================================

CURIOSITY_FLAGS = [
    {"id": "F1", "name": "CET1 Margin Squeeze", "level": "WATCH",
     "description": "CET1 below 9.5%, approaching regulatory floor"},
    {"id": "F2", "name": "NPL Outlier", "level": "REJECT",
     "description": "NPL > peer mean + 2σ, severe asset quality concern"},
    {"id": "F3", "name": "Provisioning Inadequacy", "level": "WATCH",
     "description": "PCR in caution zone (120-160%)"},
    {"id": "F4", "name": "NIM Critical", "level": "WATCH",
     "description": "NIM below 1.0%, severe margin compression"},
    {"id": "F5", "name": "Leverage-Inflated ROE", "level": "WATCH",
     "description": "ROE > p75 but ROA < 0.3%, returns inflated by leverage"},
    {"id": "F6", "name": "Unsustainable DPR", "level": "WATCH",
     "description": "Dividend payout ratio exceeds 60%"},
    {"id": "F7", "name": "DPS Decline", "level": "WATCH",
     "description": "DPS declined >30% YoY (requires multi-period data)"},
    {"id": "F8", "name": "Cost-Income Elevated", "level": "INFO",
     "description": "Cost-income ratio exceeds 60%"},
    {"id": "F9", "name": "Profitability Concern", "level": "INFO",
     "description": "ROE below 5%"},
    {"id": "F10", "name": "Thin Capital Buffer", "level": "WATCH",
     "description": "Total CAR below 12%"},
    {"id": "F11", "name": "Data Quality Poor", "level": "INFO",
     "description": "Multiple critical fields missing"},
    {"id": "F-NCO", "name": "Write-off Ratio", "level": "INFO",
     "description": "Reserved: API data unavailable for write-off ratio"},
]

# ============================================================
# PB Scoring Thresholds (from compute_scores.py)
# ============================================================

PB_SCORE_MAP = [
    (0.3, 20),   # <= 0.3: potential value trap
    (0.5, 50),
    (0.8, 80),
    (1.0, 90),
    (1.5, 60),
    (float("inf"), 30),  # > 1.5: expensive
]

# DPR Scoring Thresholds
DPR_SCORE_MAP = [
    (15, 20),    # < 15%: accumulation-type, no dividend value
    (30, 60),
    (50, 85),
    (60, 70),
    (float("inf"), 20),  # > 60%: unsustainable
]

# EPS Yield Scoring Thresholds
EPS_YIELD_SCORE_MAP = [
    (0.02, 10),
    (0.04, 30),
    (0.06, 50),
    (0.10, 75),
    (float("inf"), 90),
]

# ============================================================
# Index.csv Column Definition (ARCHITECTURE-v1 §2.2)
# ============================================================

INDEX_COLUMNS = ["code", "name", "type", "pb", "roe", "npl", "car", "nim", "mcap_rank"]

# ============================================================
# Embedding Configuration (ARCHITECTURE-v1 §4)
# ============================================================

import os

EMBEDDING_API_URL = os.environ.get(
    "EMBEDDING_API_URL",
    "http://localhost:8000/v1/embeddings",
)
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL",
    "text-embedding-3-small",
)
DEFAULT_N_CLUSTERS = 4

# ============================================================
# Pipeline Metadata
# ============================================================

PIPELINE_TIMEOUT_MINUTES = 20
PIPELINE_VERSION = "v1"
TOTAL_BANKS = 42
TARGET_CANDIDATES_MIN = 10
TARGET_CANDIDATES_MAX = 15

# ============================================================
# Helper Functions
# ============================================================

def get_bank_name(code):
    return BANK_NAMES.get(code, "Unknown")

def get_bank_group(code):
    return BANK_GROUPS.get(code, "unknown")

def get_type_override(code):
    return TYPE_OVERRIDES.get(code)

def code_to_secid(code):
    """Convert SH601398 -> 1.601398, SZ000001 -> 0.000001"""
    if code.startswith("SH"):
        return f"1.{code[2:]}"
    elif code.startswith("SZ"):
        return f"0.{code[2:]}"
    return code


if __name__ == "__main__":
    print(f"bank_constants loaded: {len(BANK_LIST)} banks, version {PIPELINE_VERSION}")
