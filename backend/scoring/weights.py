"""
评分权重配置
"""
from backend.config import SCORING_WEIGHTS

# 默认权重（均衡）
DEFAULT_WEIGHTS = SCORING_WEIGHTS.copy()

# 激进型（更重技术面和动量）
AGGRESSIVE_WEIGHTS = {
    "technical": 0.40,
    "sentiment": 0.15,
    "fund_flow": 0.15,
    "momentum": 0.20,
    "volume": 0.10,
}

# 保守型（更重基本面和资金流）
CONSERVATIVE_WEIGHTS = {
    "technical": 0.25,
    "sentiment": 0.25,
    "fund_flow": 0.25,
    "momentum": 0.10,
    "volume": 0.15,
}

# 短线交易型（更重资金流和成交量）
SHORT_TERM_WEIGHTS = {
    "technical": 0.25,
    "sentiment": 0.15,
    "fund_flow": 0.30,
    "momentum": 0.15,
    "volume": 0.15,
}

WEIGHT_PROFILES = {
    "default": DEFAULT_WEIGHTS,
    "aggressive": AGGRESSIVE_WEIGHTS,
    "conservative": CONSERVATIVE_WEIGHTS,
    "short_term": SHORT_TERM_WEIGHTS,
}


def get_weights(profile: str = "default") -> dict:
    """获取权重配置"""
    return WEIGHT_PROFILES.get(profile, DEFAULT_WEIGHTS).copy()
