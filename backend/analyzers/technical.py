"""
技术指标分析器 - 使用pure pandas/numpy计算MA/MACD/RSI/KDJ/Bollinger等指标
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np
from sqlalchemy import text
from loguru import logger

from backend.database import async_session
from backend.utils.cache import history_cache

CST = ZoneInfo("Asia/Shanghai")


def compute_indicators(df: pd.DataFrame) -> dict:
    """
    计算所有技术指标
    输入: 包含 OHLCV 列的DataFrame (按日期升序)
    返回: 指标字典
    """
    if df is None or df.empty or len(df) < 5:
        return _empty_indicators()

    try:
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)

        indicators = {}

        # ---- MA均线 ----
        indicators["ma5"] = float(close.rolling(5).mean().iloc[-1]) if len(close) >= 5 else None
        indicators["ma10"] = float(close.rolling(10).mean().iloc[-1]) if len(close) >= 10 else None
        indicators["ma20"] = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
        indicators["ma60"] = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else None

        # ---- MACD (12, 26, 9) ----
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_bar = 2 * (dif - dea)

        indicators["macd_dif"] = float(dif.iloc[-1]) if not dif.empty else None
        indicators["macd_dea"] = float(dea.iloc[-1]) if not dea.empty else None
        indicators["macd_bar"] = float(macd_bar.iloc[-1]) if not macd_bar.empty else None

        # ---- RSI (6, 12, 24) ----
        for period in [6, 12, 24]:
            if len(close) >= period + 1:
                delta = close.diff()
                gain = delta.clip(lower=0)
                loss = (-delta).clip(lower=0)
                avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
                rs = avg_gain / avg_loss.replace(0, np.nan)
                rsi = 100 - (100 / (1 + rs))
                indicators[f"rsi_{period}"] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
            else:
                indicators[f"rsi_{period}"] = None

        # ---- KDJ (9, 3, 3) ----
        if len(close) >= 9:
            low_9 = low.rolling(9).min()
            high_9 = high.rolling(9).max()
            rsv = (close - low_9) / (high_9 - low_9).replace(0, np.nan) * 100

            k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
            d = k.ewm(alpha=1 / 3, adjust=False).mean()
            j = 3 * k - 2 * d

            indicators["kdj_k"] = float(k.iloc[-1]) if not pd.isna(k.iloc[-1]) else None
            indicators["kdj_d"] = float(d.iloc[-1]) if not pd.isna(d.iloc[-1]) else None
            indicators["kdj_j"] = float(j.iloc[-1]) if not pd.isna(j.iloc[-1]) else None
        else:
            indicators["kdj_k"] = indicators["kdj_d"] = indicators["kdj_j"] = None

        # ---- Bollinger Bands (20, 2) ----
        if len(close) >= 20:
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            indicators["boll_mid"] = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else None
            indicators["boll_upper"] = float((sma20 + 2 * std20).iloc[-1]) if indicators["boll_mid"] else None
            indicators["boll_lower"] = float((sma20 - 2 * std20).iloc[-1]) if indicators["boll_mid"] else None
        else:
            indicators["boll_upper"] = indicators["boll_mid"] = indicators["boll_lower"] = None

        # ---- 成交量指标 ----
        if len(volume) >= 5:
            indicators["vol_ma5"] = float(volume.rolling(5).mean().iloc[-1])
        else:
            indicators["vol_ma5"] = None

        if len(volume) >= 20:
            vol_ma20 = volume.rolling(20).mean().iloc[-1]
            indicators["vol_ratio_vs20"] = float(volume.iloc[-1] / vol_ma20) if vol_ma20 > 0 else 1.0
        else:
            indicators["vol_ratio_vs20"] = None

        return indicators

    except Exception as e:
        logger.error(f"计算技术指标异常: {e}")
        return _empty_indicators()


def _empty_indicators() -> dict:
    return {
        "ma5": None, "ma10": None, "ma20": None, "ma60": None,
        "macd_dif": None, "macd_dea": None, "macd_bar": None,
        "rsi_6": None, "rsi_12": None, "rsi_24": None,
        "kdj_k": None, "kdj_d": None, "kdj_j": None,
        "boll_upper": None, "boll_mid": None, "boll_lower": None,
        "vol_ma5": None, "vol_ratio_vs20": None,
    }


async def compute_and_save_indicators(codes: list[str]):
    """
    批量计算并保存技术指标
    """
    now_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    computed = 0

    async with async_session() as session:
        for code in codes:
            try:
                # 从内存缓存获取历史数据
                df = history_cache.get(code)
                if df is None or df.empty:
                    # 尝试从数据库加载
                    result = await session.execute(
                        text("""
                            SELECT trade_date, open, high, low, close, volume
                            FROM stock_daily
                            WHERE code = :code
                            ORDER BY trade_date ASC
                        """),
                        {"code": code}
                    )
                    rows = result.fetchall()
                    if not rows:
                        continue
                    df = pd.DataFrame(
                        rows,
                        columns=["trade_date", "open", "high", "low", "close", "volume"]
                    )
                    history_cache[code] = df

                indicators = compute_indicators(df)

                # 保存到数据库
                await session.execute(
                    text("""
                        INSERT OR REPLACE INTO technical_indicators (
                            code, ma5, ma10, ma20, ma60,
                            macd_dif, macd_dea, macd_bar,
                            rsi_6, rsi_12, rsi_24,
                            kdj_k, kdj_d, kdj_j,
                            boll_upper, boll_mid, boll_lower,
                            vol_ma5, vol_ratio_vs20, computed_at
                        ) VALUES (
                            :code, :ma5, :ma10, :ma20, :ma60,
                            :macd_dif, :macd_dea, :macd_bar,
                            :rsi_6, :rsi_12, :rsi_24,
                            :kdj_k, :kdj_d, :kdj_j,
                            :boll_upper, :boll_mid, :boll_lower,
                            :vol_ma5, :vol_ratio_vs20, :computed_at
                        )
                    """),
                    {**indicators, "code": code, "computed_at": now_str}
                )
                computed += 1

            except Exception as e:
                logger.debug(f"计算指标失败 {code}: {e}")
                continue

        await session.commit()

    logger.info(f"技术指标计算完成: {computed} 只")


async def get_indicators(code: str) -> dict:
    """获取单只股票的技术指标"""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT * FROM technical_indicators WHERE code = :code"),
            {"code": code}
        )
        row = result.fetchone()
        if row:
            return dict(row._mapping)
        return _empty_indicators()
