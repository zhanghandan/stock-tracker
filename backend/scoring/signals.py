"""
买卖信号生成器 - 综合技术指标给出交易建议
"""
from backend.config import SIGNAL_THRESHOLDS


def generate_signal(
    composite_score: float,
    technical_indicators: dict | None = None,
    change_pct: float = 0.0,
    volume_ratio: float = 1.0,
) -> str:
    """
    根据综合评分和辅助指标生成买卖信号

    返回:
        STRONG_BUY, BUY, HOLD, WEAK_HOLD, SELL
    """
    if composite_score >= SIGNAL_THRESHOLDS["STRONG_BUY"]:
        # 需要同时满足：上涨 + 有量
        if change_pct > 0 and volume_ratio >= 1.2:
            return "STRONG_BUY"
        else:
            return "BUY"

    elif composite_score >= SIGNAL_THRESHOLDS["BUY"]:
        return "BUY"

    elif composite_score >= SIGNAL_THRESHOLDS["HOLD"]:
        return "HOLD"

    elif composite_score >= SIGNAL_THRESHOLDS["WEAK_HOLD"]:
        return "WEAK_HOLD"

    else:
        return "SELL"


def get_signal_color(signal: str) -> str:
    """获取信号对应的颜色"""
    colors = {
        "STRONG_BUY": "#cf1322",  # 深红(中国红=涨)
        "BUY": "#f5222d",         # 红色
        "HOLD": "#faad14",        # 黄色
        "WEAK_HOLD": "#1890ff",   # 蓝色
        "SELL": "#52c41a",        # 绿色
    }
    return colors.get(signal, "#999")


def get_signal_zh(signal: str) -> str:
    """信号中英文转换"""
    mapping = {
        "STRONG_BUY": "强烈买入",
        "BUY": "买入",
        "HOLD": "持有",
        "WEAK_HOLD": "观望",
        "SELL": "卖出",
    }
    return mapping.get(signal, signal)


def generate_signal_reason(
    composite_score: float,
    technical_score: float,
    sentiment_score: float,
    fund_flow_score: float,
    momentum_score: float,
    volume_score: float,
    change_pct: float,
    volume_ratio: float,
) -> str:
    """
    生成买卖信号的文字解释
    """
    reasons = []

    signal = generate_signal(composite_score, change_pct=change_pct, volume_ratio=volume_ratio)

    if signal in ("STRONG_BUY", "BUY"):
        # 找出最强的3个因子
        factors = [
            ("技术面", technical_score),
            ("新闻情绪", sentiment_score),
            ("资金流向", fund_flow_score),
            ("动量趋势", momentum_score),
            ("成交量", volume_score),
        ]
        factors.sort(key=lambda x: x[1], reverse=True)
        top_factors = [f"{name}({score:.0f}分)" for name, score in factors[:3]]
        reasons.append(f"综合评分{composite_score:.1f}，主要驱动因素：{'、'.join(top_factors)}")

        if change_pct > 0:
            reasons.append(f"当日上涨{change_pct:.2f}%")
        if volume_ratio >= 1.5:
            reasons.append(f"成交量放大至{volume_ratio:.1f}倍")

    elif signal == "HOLD":
        reasons.append(f"综合评分{composite_score:.1f}，各项指标中性偏多，建议持有观察")

    elif signal == "WEAK_HOLD":
        reasons.append(f"综合评分{composite_score:.1f}，信号偏弱，建议观望等待明确信号")

    else:  # SELL
        reasons.append(f"综合评分{composite_score:.1f}，多项指标偏空，建议回避")
        if change_pct < 0:
            reasons.append(f"当日下跌{abs(change_pct):.2f}%")

    return "；".join(reasons)
