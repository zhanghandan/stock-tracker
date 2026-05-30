"""
A股交易时间判断工具
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")

MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)


def is_trading_time(dt: datetime | None = None) -> bool:
    """
    判断当前是否为A股连续竞价交易时段
    周一至周五 9:30-11:30, 13:00-15:00
    """
    if dt is None:
        dt = datetime.now(CST)

    if dt.weekday() >= 5:  # 周六日
        return False

    t = dt.time()
    morning = MORNING_START <= t < MORNING_END
    afternoon = AFTERNOON_START <= t < AFTERNOON_END

    return morning or afternoon


def is_trading_day(dt: datetime | None = None) -> bool:
    """判断是否为交易日（简化版，不含节假日）"""
    if dt is None:
        dt = datetime.now(CST)
    return dt.weekday() < 5


def is_lunch_break(dt: datetime | None = None) -> bool:
    """判断是否为午间休市时间"""
    if dt is None:
        dt = datetime.now(CST)

    if dt.weekday() >= 5:
        return False

    t = dt.time()
    return MORNING_END <= t < AFTERNOON_START


def get_market_status(dt: datetime | None = None) -> str:
    """
    获取当前市场状态
    返回: 'open' | 'lunch_break' | 'closed'
    """
    if dt is None:
        dt = datetime.now(CST)

    if is_trading_time(dt):
        return "open"
    elif is_lunch_break(dt):
        return "lunch_break"
    else:
        return "closed"


def next_session(dt: datetime | None = None) -> str:
    """
    返回下一个交易时段描述
    """
    if dt is None:
        dt = datetime.now(CST)

    t = dt.time()

    if dt.weekday() >= 5:
        # 周末 -> 下周一
        days_ahead = 7 - dt.weekday()
        return f"下周一 9:30"

    if t < MORNING_START:
        return "今天 9:30"
    elif t < MORNING_END:
        return "上午交易中"
    elif t < AFTERNOON_START:
        return "今天 13:00"
    elif t < AFTERNOON_END:
        return "下午交易中"
    else:
        if dt.weekday() == 4:  # 周五
            return "下周一 9:30"
        else:
            return "明天 9:30"
