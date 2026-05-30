"""
成交量/资金流分析器
"""
import math
from sqlalchemy import text
from loguru import logger

from backend.database import async_session


async def analyze_volume_flow(code: str) -> dict:
    """
    分析单只股票的成交量和资金流表现
    返回评分 0-100
    """
    score = 50.0  # 基础分
    details = {}

    async with async_session() as session:
        # 获取资金流向
        ff_result = await session.execute(
            text("""
                SELECT main_net_pct, super_large_inflow, large_inflow,
                       medium_inflow, small_inflow
                FROM fund_flow
                WHERE code = :code
                ORDER BY flow_date DESC
                LIMIT 1
            """),
            {"code": code}
        )
        ff = ff_result.fetchone()

        if ff:
            main_pct = ff[0] or 0
            super_large = ff[1] or 0
            large = ff[2] or 0
            medium = ff[3] or 0
            small = ff[4] or 0

            # 主力净流入占比评分 (0-40)
            # sigmoid映射: -10% → 0, +10% → 40
            if main_pct > 0:
                flow_score = min(40, main_pct * 4)
            else:
                flow_score = max(0, 20 + main_pct * 2)

            # 超大单+大单 vs 散户 (0-20)
            institution = super_large + large
            retail = medium + small
            total = institution + retail
            if total != 0:
                inst_ratio = institution / total if total > 0 else 0
            else:
                inst_ratio = 0
            inst_bonus = min(20, max(0, (inst_ratio - 0.3) * 50))

            score = 30 + flow_score + inst_bonus
            details = {
                "main_net_pct": round(main_pct, 2),
                "institution_flow": round(institution / 1e8, 2) if abs(institution) > 1e4 else 0,
                "retail_flow": round(retail / 1e8, 2) if abs(retail) > 1e4 else 0,
                "institution_ratio": round(inst_ratio, 3),
            }

        # 获取成交量数据（从实时行情）
        rt_result = await session.execute(
            text("""
                SELECT volume_ratio, turnover_rate
                FROM stock_realtime
                WHERE code = :code
            """),
            {"code": code}
        )
        rt = rt_result.fetchone()

        if rt:
            vol_ratio = rt[0] or 1.0
            turnover = rt[1] or 0

            # 量比评分 (0-20)
            if vol_ratio > 2.0:
                vol_bonus = 20
            elif vol_ratio > 1.5:
                vol_bonus = 16
            elif vol_ratio > 1.0:
                vol_bonus = 12
            elif vol_ratio > 0.5:
                vol_bonus = 8
            else:
                vol_bonus = 4

            # 换手率健康度 (0-20)
            if 3 <= turnover <= 10:
                turnover_bonus = 20
            elif 1 <= turnover < 3:
                turnover_bonus = 15
            elif 10 < turnover <= 20:
                turnover_bonus = 10
            elif turnover < 1:
                turnover_bonus = 5
            else:
                turnover_bonus = 3

            # 合并资金流和成交量评分
            # 资金流占60%，成交量占40%
            volume_part = vol_bonus + turnover_bonus
            if not details:
                # 没有资金流数据，纯成交量评分
                score = volume_part * 2.5  # 40分制转100分制

            details.update({
                "volume_ratio": round(vol_ratio, 2),
                "turnover_rate": round(turnover, 2),
                "vol_bonus": vol_bonus,
                "turnover_bonus": turnover_bonus,
            })

    return {
        "score": round(min(100, max(0, score)), 2),
        "details": details,
    }


async def compute_volume_scores(codes: list[str]) -> dict[str, dict]:
    """批量计算成交量/资金流评分"""
    results = {}
    for code in codes:
        try:
            results[code] = await analyze_volume_flow(code)
        except Exception as e:
            logger.debug(f"分析资金流失败 {code}: {e}")
            results[code] = {"score": 50.0, "details": {}}
    return results
