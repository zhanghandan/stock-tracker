"""
综合评分排名引擎 - 核心评分逻辑
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import text
from loguru import logger

from backend.database import async_session
from backend.config import (
    SCORING_WEIGHTS, EXCLUDE_ST_STOCKS,
    EXCLUDE_PRICE_BELOW, EXCLUDE_PE_ABOVE, PE_NEGATIVE_PENALTY,
)
from backend.analyzers.technical import compute_and_save_indicators
from backend.analyzers.sentiment import get_stock_sentiment
from backend.analyzers.volume_flow import compute_volume_scores
from backend.scoring.signals import generate_signal

CST = ZoneInfo("Asia/Shanghai")


async def compute_technical_score(code: str, indicators: dict) -> float:
    """
    计算技术面评分 (0-100)
    基于均线排列、MACD、RSI、KDJ、Bollinger、成交量
    """
    score = 0.0

    # ---- 1. MA均线排列 (0-25分) ----
    ma5 = indicators.get("ma5")
    ma10 = indicators.get("ma10")
    ma20 = indicators.get("ma20")
    ma60 = indicators.get("ma60")

    if all(v is not None for v in [ma5, ma10, ma20, ma60]):
        # 多头排列 MA5>MA10>MA20>MA60
        if ma5 > ma10 > ma20 > ma60:
            score += 25
        elif ma5 > ma10 > ma20:
            score += 18
        elif ma5 > ma10:
            score += 12
        elif ma5 > ma20:
            score += 8
        # 空头排列
        elif ma5 < ma10 < ma20:
            score += 3
        elif ma5 < ma10:
            score += 1
        else:
            score += 5
    elif ma5 is not None and ma10 is not None:
        if ma5 > ma10:
            score += 12
        else:
            score += 5

    # ---- 2. MACD (0-20分) ----
    dif = indicators.get("macd_dif")
    dea = indicators.get("macd_dea")
    bar = indicators.get("macd_bar")

    if all(v is not None for v in [dif, dea, bar]):
        # DIF在DEA上方 = 多头
        if dif > dea:
            score += 10
            # MACD柱扩大 = 趋势加强
            if bar > 0:
                score += min(10, bar * 20)  # bar越大加分越多
        else:
            score += 3
            if bar < 0:
                score += max(0, 2 + bar * 5)  # 负bar扣分
    elif bar is not None:
        if bar > 0:
            score += 10

    # ---- 3. RSI (0-15分) ----
    rsi = indicators.get("rsi_12") or indicators.get("rsi_6")
    if rsi is not None:
        if 40 <= rsi <= 70:
            score += 15
        elif 30 <= rsi < 40:
            score += 10  # 可能超卖反弹
        elif rsi > 70:
            score += 8   # 超买但强势
        elif rsi < 30:
            score += 5   # 深度超卖
        else:
            score += 7

    # ---- 4. KDJ (0-15分) ----
    k = indicators.get("kdj_k")
    d = indicators.get("kdj_d")
    j = indicators.get("kdj_j")

    if all(v is not None for v in [k, d, j]):
        # K在D上方 = 金叉区域
        if k > d:
            score += 10
            if j < 20:  # 超卖区金叉
                score += 5
            elif j > 80:  # 超买区但金叉
                score += 2
        else:
            score += 3
            if j > 80:  # 超买死叉
                score += 1
            elif j < 20:  # 超卖但死叉
                score += 4
    elif k is not None and d is not None:
        score += 10 if k > d else 3

    # ---- 5. Bollinger Bands (0-15分) ----
    boll_upper = indicators.get("boll_upper")
    boll_mid = indicators.get("boll_mid")
    boll_lower = indicators.get("boll_lower")

    if all(v is not None for v in [boll_upper, boll_mid, boll_lower]):
        # 获取当前价格
        async with async_session() as session:
            result = await session.execute(
                text("SELECT latest_price FROM stock_realtime WHERE code = :code"),
                {"code": code}
            )
            price_row = result.fetchone()
            price = price_row[0] if price_row else None

        if price is not None and boll_mid > 0:
            # 价格在中轨上方 = 偏多
            position = (price - boll_mid) / (boll_upper - boll_lower + 0.001)
            if 0 < position < 0.5:
                score += 15
            elif position >= 0.5:
                score += 10  # 接近上轨，强势但需注意回调
            elif -0.3 < position <= 0:
                score += 8   # 略偏弱
            elif position <= -0.3:
                score += 5   # 接近下轨
        else:
            score += 8
    else:
        score += 8

    # ---- 6. 成交量信号 (0-10分) ----
    vol_ratio = indicators.get("vol_ratio_vs20")
    if vol_ratio is not None:
        if 1.5 <= vol_ratio <= 3.0:
            score += 10
        elif 1.2 <= vol_ratio < 1.5:
            score += 7
        elif 0.8 <= vol_ratio < 1.2:
            score += 5
        elif vol_ratio > 3.0:
            score += 6  # 过度放量
        else:
            score += 3
    else:
        score += 5

    return min(100, max(0, score))


async def compute_momentum_score(code: str) -> float:
    """
    计算动量评分 (0-100)
    基于5日/20日涨跌幅和价格位置
    """
    async with async_session() as session:
        # 实时涨跌幅
        rt_result = await session.execute(
            text("""
                SELECT change_pct, change_60d, change_ytd, high, low, latest_price
                FROM stock_realtime WHERE code = :code
            """),
            {"code": code}
        )
        rt = rt_result.fetchone()

        if not rt:
            return 50.0

        change_pct = rt[0] or 0
        change_60d = rt[1] or 0
        change_ytd = rt[2] or 0
        high = rt[3]
        low = rt[4]
        price = rt[5]

        # 日涨跌贡献 (0-35)
        if change_pct > 5:
            daily_score = 35
        elif change_pct > 2:
            daily_score = 30
        elif change_pct > 0:
            daily_score = 20 + change_pct * 2
        elif change_pct > -2:
            daily_score = 15 + change_pct * 2.5
        elif change_pct > -5:
            daily_score = 10
        else:
            daily_score = 3

        # 60日趋势 (0-30)
        if change_60d is not None:
            if change_60d > 20:
                trend_score = 30
            elif change_60d > 10:
                trend_score = 25
            elif change_60d > 0:
                trend_score = 18
            elif change_60d > -10:
                trend_score = 10
            elif change_60d > -20:
                trend_score = 5
            else:
                trend_score = 2
        else:
            trend_score = 15

        # YTD趋势 (0-15)
        if change_ytd is not None:
            if change_ytd > 30:
                ytd_score = 15
            elif change_ytd > 15:
                ytd_score = 12
            elif change_ytd > 0:
                ytd_score = 8
            else:
                ytd_score = 4
        else:
            ytd_score = 8

        # 价格位置 vs 日内范围 (0-20)
        if high and low and price and high != low:
            position = (price - low) / (high - low)
            if position > 0.7:
                pos_score = 20
            elif position > 0.5:
                pos_score = 15
            elif position > 0.3:
                pos_score = 10
            else:
                pos_score = 5
        else:
            pos_score = 10

        return min(100, daily_score + trend_score + ytd_score + pos_score)


async def run_scoring_pipeline(codes: list[str], weight_profile: str = "default") -> list[dict]:
    """
    运行完整评分流程
    1. 计算技术指标
    2. 计算各子评分
    3. 加权综合
    4. 排名输出Top50
    """
    from backend.scoring.weights import get_weights

    weights = get_weights(weight_profile)
    now_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

    # Step 1: 计算技术指标
    logger.info("Step 1/5: 计算技术指标...")
    await compute_and_save_indicators(codes)

    # Step 2: 获取成交量/资金流评分
    logger.info("Step 2/5: 计算资金流/成交量评分...")
    volume_results = await compute_volume_scores(codes)

    # Step 3: 逐股计算综合评分
    logger.info("Step 3/5: 计算综合评分...")
    stock_scores = []

    async with async_session() as session:
        for code in codes:
            try:
                # 获取实时数据
                rt_result = await session.execute(
                    text("""
                        SELECT name, latest_price, change_pct, pe_ttm,
                               volume_ratio, turnover_rate
                        FROM stock_realtime WHERE code = :code
                    """),
                    {"code": code}
                )
                rt = rt_result.fetchone()
                if not rt:
                    continue

                name = rt[0]
                price = rt[1]
                change_pct = rt[2] or 0
                pe_ttm = rt[3]
                volume_ratio = rt[4] or 1.0

                # ----- 技术评分 -----
                ind_result = await session.execute(
                    text("SELECT * FROM technical_indicators WHERE code = :code"),
                    {"code": code}
                )
                ind_row = ind_result.fetchone()
                indicators = dict(ind_row._mapping) if ind_row else {}

                technical_score = await compute_technical_score(code, indicators)

                # ----- 情绪评分 -----
                sentiment_result = await get_stock_sentiment(code)
                sentiment_score = sentiment_result["score"]

                # ----- 资金流/成交量评分 -----
                vol_result = volume_results.get(code, {"score": 50.0})
                fund_flow_score = vol_result["score"]

                # ----- 动量评分 -----
                momentum_score = await compute_momentum_score(code)

                # ----- 成交量评分（纯成交量维度） -----
                vol_ratio_score = _compute_pure_volume_score(indicators, volume_ratio)

                # ----- 综合评分 -----
                composite = (
                    technical_score * weights["technical"] +
                    sentiment_score * weights["sentiment"] +
                    fund_flow_score * weights["fund_flow"] +
                    momentum_score * weights["momentum"] +
                    vol_ratio_score * weights["volume"]
                )

                # PE修正
                if pe_ttm is not None:
                    if pe_ttm < 0:
                        composite += PE_NEGATIVE_PENALTY
                    elif pe_ttm > EXCLUDE_PE_ABOVE:
                        composite += PE_NEGATIVE_PENALTY

                composite = max(0, min(100, composite))

                # 生成买卖信号
                signal = generate_signal(
                    composite,
                    technical_indicators=indicators,
                    change_pct=change_pct,
                    volume_ratio=volume_ratio,
                )

                stock_scores.append({
                    "code": code,
                    "name": name,
                    "latest_price": price,
                    "change_pct": change_pct,
                    "composite_score": round(composite, 2),
                    "technical_score": round(technical_score, 2),
                    "sentiment_score": round(sentiment_score, 2),
                    "fund_flow_score": round(fund_flow_score, 2),
                    "momentum_score": round(momentum_score, 2),
                    "volume_score": round(vol_ratio_score, 2),
                    "technical_signal": signal,
                    "indicators": {
                        "ma5": indicators.get("ma5"),
                        "ma10": indicators.get("ma10"),
                        "ma20": indicators.get("ma20"),
                        "rsi_6": indicators.get("rsi_6"),
                        "macd_bar": indicators.get("macd_bar"),
                        "kdj_k": indicators.get("kdj_k"),
                        "boll_upper": indicators.get("boll_upper"),
                        "boll_mid": indicators.get("boll_mid"),
                        "boll_lower": indicators.get("boll_lower"),
                    },
                })

            except Exception as e:
                logger.debug(f"评分 {code} 失败: {e}")
                continue

    # Step 4: 排名
    stock_scores.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, s in enumerate(stock_scores):
        s["rank"] = i + 1

    # Step 5: 保存到数据库
    logger.info(f"Step 5/5: 保存排名结果 Top{min(50, len(stock_scores))}...")
    await _save_scores_to_db(stock_scores[:50], now_str)

    return stock_scores[:50]


def _compute_pure_volume_score(indicators: dict, volume_ratio: float) -> float:
    """纯成交量维度评分 (0-100)"""
    score = 40.0

    # 量比
    if volume_ratio >= 3.0:
        score += 30
    elif volume_ratio >= 2.0:
        score += 25
    elif volume_ratio >= 1.5:
        score += 20
    elif volume_ratio >= 1.0:
        score += 15
    elif volume_ratio >= 0.5:
        score += 10
    else:
        score += 5

    # 量/20日均量
    vol_ratio20 = indicators.get("vol_ratio_vs20")
    if vol_ratio20 is not None:
        if vol_ratio20 >= 1.5:
            score += 30
        elif vol_ratio20 >= 1.0:
            score += 20
        else:
            score += 10
    else:
        score += 15

    return min(100, score)


async def _save_scores_to_db(scores: list[dict], now_str: str):
    """保存评分结果到数据库"""
    async with async_session() as session:
        # 清空旧排名
        await session.execute(text("DELETE FROM stock_scores"))

        for s in scores:
            await session.execute(
                text("""
                    INSERT INTO stock_scores (
                        code, rank, composite_score, technical_score,
                        sentiment_score, fund_flow_score, momentum_score,
                        volume_score, technical_signal, scored_at
                    ) VALUES (
                        :code, :rank, :composite, :tech, :sent, :flow,
                        :mom, :vol, :signal, :scored_at
                    )
                """),
                {
                    "code": s["code"],
                    "rank": s["rank"],
                    "composite": s["composite_score"],
                    "tech": s["technical_score"],
                    "sent": s["sentiment_score"],
                    "flow": s["fund_flow_score"],
                    "mom": s["momentum_score"],
                    "vol": s["volume_score"],
                    "signal": s["technical_signal"],
                    "scored_at": now_str,
                }
            )
        await session.commit()

    logger.info("评分排名已保存到数据库")


async def get_top_rankings(limit: int = 50) -> list[dict]:
    """获取Top排名"""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT s.code, s.rank, s.composite_score, s.technical_score,
                       s.sentiment_score, s.fund_flow_score, s.momentum_score,
                       s.volume_score, s.technical_signal, s.scored_at,
                       r.name, r.latest_price, r.change_pct,
                       r.volume_ratio, r.turnover_rate, r.pe_ttm, r.pb,
                       r.total_mv, r.change_60d
                FROM stock_scores s
                JOIN stock_realtime r ON s.code = r.code
                ORDER BY s.rank ASC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        rows = result.fetchall()
        return [_score_row_to_dict(row) for row in rows]


def _score_row_to_dict(row) -> dict:
    """将数据库行转为字典"""
    return {
        "code": row[0],
        "rank": row[1],
        "composite_score": row[2],
        "technical_score": row[3],
        "sentiment_score": row[4],
        "fund_flow_score": row[5],
        "momentum_score": row[6],
        "volume_score": row[7],
        "technical_signal": row[8],
        "scored_at": row[9],
        "name": row[10],
        "latest_price": row[11],
        "change_pct": row[12],
        "volume_ratio": row[13],
        "turnover_rate": row[14],
        "pe_ttm": row[15],
        "pb": row[16],
        "total_mv": row[17],
        "change_60d": row[18],
    }
