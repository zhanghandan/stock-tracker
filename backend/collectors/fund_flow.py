"""
资金流向数据采集器
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text
from loguru import logger

from backend.database import async_session
from backend.collectors.base import sync_with_retry
from backend.utils.cache import fund_flow_cache

CST = ZoneInfo("Asia/Shanghai")


@sync_with_retry()
def _fetch_fund_flow_sync() -> pd.DataFrame | None:
    """同步获取个股资金流向排名"""
    import akshare as ak
    try:
        # 获取今日个股资金流向
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        return df
    except Exception as e:
        logger.warning(f"获取资金流向失败: {e}")
        return None


async def fetch_fund_flow() -> pd.DataFrame | None:
    """获取资金流向数据"""
    # 检查缓存
    cached = fund_flow_cache.get("fund_flow_df")
    if cached is not None:
        return cached

    try:
        df = await asyncio.to_thread(_fetch_fund_flow_sync)
        if df is not None and not df.empty:
            fund_flow_cache.set("fund_flow_df", df)
            logger.debug(f"资金流向获取成功: {len(df)} 条")
        return df
    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        return None


async def save_fund_flow_to_db(df: pd.DataFrame):
    """保存资金流向数据"""
    if df is None or df.empty:
        return

    today_str = datetime.now(CST).strftime("%Y-%m-%d")
    now_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

    # 列名映射（akshare中文列名）
    column_mapping = {
        "代码": "code", "名称": "name",
        "主力净流入-净额": "main_net_inflow",
        "主力净流入-净占比": "main_net_pct",
        "超大单净流入-净额": "super_large_inflow",
        "大单净流入-净额": "large_inflow",
        "中单净流入-净额": "medium_inflow",
        "小单净流入-净额": "small_inflow",
    }

    df = df.rename(columns=column_mapping)

    async with async_session() as session:
        count = 0
        for _, row in df.iterrows():
            try:
                code = str(row.get("code", ""))
                if not code:
                    continue

                await session.execute(
                    text("""
                        INSERT OR REPLACE INTO fund_flow (
                            code, flow_date, main_net_inflow, main_net_pct,
                            super_large_inflow, large_inflow, medium_inflow, small_inflow,
                            updated_at
                        ) VALUES (
                            :code, :flow_date, :main_net_inflow, :main_net_pct,
                            :super_large_inflow, :large_inflow, :medium_inflow, :small_inflow,
                            :updated_at
                        )
                    """),
                    {
                        "code": code,
                        "flow_date": today_str,
                        "main_net_inflow": _sf(row.get("main_net_inflow")),
                        "main_net_pct": _sf(row.get("main_net_pct")),
                        "super_large_inflow": _sf(row.get("super_large_inflow")),
                        "large_inflow": _sf(row.get("large_inflow")),
                        "medium_inflow": _sf(row.get("medium_inflow")),
                        "small_inflow": _sf(row.get("small_inflow")),
                        "updated_at": now_str,
                    }
                )
                count += 1
            except Exception as e:
                logger.debug(f"写入资金流向失败 {code}: {e}")
                continue

        await session.commit()
    logger.info(f"资金流向写入完成: {count} 条")


def _sf(val) -> float | None:
    if val is None or val == "-":
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None
