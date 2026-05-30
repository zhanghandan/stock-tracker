"""
历史K线数据采集器
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text
from loguru import logger

from backend.database import async_session
from backend.collectors.base import sync_with_retry
from backend.config import HISTORY_DAYS

CST = ZoneInfo("Asia/Shanghai")


@sync_with_retry()
def _fetch_history_sync(code: str, period: str = "daily", days: int = HISTORY_DAYS) -> pd.DataFrame | None:
    """同步获取单只股票历史K线"""
    import akshare as ak
    from datetime import timedelta

    try:
        # 根据股票代码判断市场
        if code.startswith("6"):
            adjust = "qfq"  # 前复权
        else:
            adjust = "qfq"

        end_date = datetime.now(CST).date()
        start_date = (end_date - timedelta(days=days + 10)).isoformat()  # 多拿10天，含非交易日

        df = ak.stock_zh_a_hist(
            symbol=code,
            period=period,
            start_date=start_date,
            end_date=end_date.isoformat(),
            adjust=adjust
        )

        # akshare返回的列名可能是中文
        if df is not None and not df.empty:
            # 取最近N天
            df = df.tail(days)
            return df
        return None

    except Exception as e:
        logger.debug(f"获取 {code} 历史数据失败: {e}")
        return None


async def fetch_all_history(codes: list[str]) -> dict[str, pd.DataFrame]:
    """
    批量获取所有股票的历史K线数据
    使用信号量控制并发数
    """
    semaphore = asyncio.Semaphore(10)  # 最多10个并发请求
    results = {}

    async def fetch_one(code: str):
        async with semaphore:
            df = await asyncio.to_thread(_fetch_history_sync, code)
            return code, df

    tasks = [fetch_one(code) for code in codes]
    completed = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = 0
    for result in completed:
        if isinstance(result, Exception):
            logger.debug(f"获取历史数据异常: {result}")
            continue
        code, df = result
        if df is not None and not df.empty:
            results[code] = df
            success_count += 1

    logger.info(f"历史数据获取完成: {success_count}/{len(codes)}")
    return results


async def save_history_to_db(code: str, df: pd.DataFrame):
    """保存单只股票的历史K线到数据库"""
    if df is None or df.empty:
        return

    column_mapping = {
        "日期": "trade_date", "开盘": "open", "收盘": "close",
        "最高": "high", "最低": "low", "成交量": "volume",
        "成交额": "amount", "振幅": "amplitude",
        "涨跌幅": "change_pct", "涨跌额": "change_amt",
        "换手率": "turnover_rate",
    }

    df = df.rename(columns=column_mapping)

    async with async_session() as session:
        for _, row in df.iterrows():
            try:
                trade_date = str(row.get("trade_date", ""))
                if not trade_date:
                    continue

                # 标准化日期格式
                if len(trade_date) > 10:
                    trade_date = trade_date[:10]

                await session.execute(
                    text("""
                        INSERT OR REPLACE INTO stock_daily (
                            code, trade_date, open, high, low, close,
                            volume, amount, amplitude, change_pct, change_amt, turnover_rate
                        ) VALUES (
                            :code, :trade_date, :open, :high, :low, :close,
                            :volume, :amount, :amplitude, :change_pct, :change_amt, :turnover_rate
                        )
                    """),
                    {
                        "code": code,
                        "trade_date": trade_date,
                        "open": _sf(row.get("open")),
                        "high": _sf(row.get("high")),
                        "low": _sf(row.get("low")),
                        "close": _sf(row.get("close")),
                        "volume": _sf(row.get("volume")),
                        "amount": _sf(row.get("amount")),
                        "amplitude": _sf(row.get("amplitude")),
                        "change_pct": _sf(row.get("change_pct")),
                        "change_amt": _sf(row.get("change_amt")),
                        "turnover_rate": _sf(row.get("turnover_rate")),
                    }
                )
            except Exception as e:
                logger.debug(f"写入历史数据失败 {code}: {e}")
                continue

        await session.commit()


def _sf(val) -> float | None:
    """安全转换为float"""
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None


async def load_history_to_cache(codes: list[str]) -> dict[str, pd.DataFrame]:
    """
    从数据库加载历史数据到内存缓存
    用于快速指标计算
    """
    from backend.utils.cache import history_cache

    async with async_session() as session:
        for code in codes:
            result = await session.execute(
                text("""
                    SELECT trade_date, open, high, low, close, volume,
                           amount, change_pct, turnover_rate
                    FROM stock_daily
                    WHERE code = :code
                    ORDER BY trade_date ASC
                """),
                {"code": code}
            )
            rows = result.fetchall()
            if rows:
                df = pd.DataFrame(
                    rows,
                    columns=["trade_date", "open", "high", "low", "close",
                             "volume", "amount", "change_pct", "turnover_rate"]
                )
                history_cache[code] = df

    logger.info(f"历史数据缓存加载完成: {len(history_cache)} 只")
    return history_cache


async def seed_history_for_codes(codes: list[str], max_concurrent: int = 8, days: int = 60):
    """
    为指定股票列表获取并保存历史K线数据
    用于首次启动或增量补充
    """
    import asyncio

    # 先检查哪些股票已有历史数据
    existing_codes = set()
    async with async_session() as session:
        # SQLite不支持数组参数，分批查询
        for i in range(0, len(codes), 100):
            batch = codes[i:i + 100]
            placeholders = ",".join([f"'{c}'" for c in batch])
            result = await session.execute(
                text(f"SELECT DISTINCT code FROM stock_daily WHERE code IN ({placeholders})")
            )
            existing_codes.update(row[0] for row in result.fetchall())

    missing_codes = [c for c in codes if c not in existing_codes]
    if not missing_codes:
        logger.info(f"所有 {len(codes)} 只候选股已有历史数据")
        return 0

    logger.info(f"需要获取 {len(missing_codes)} 只股票的历史数据...")

    semaphore = asyncio.Semaphore(max_concurrent)
    fetched = 0

    async def fetch_and_save(code: str):
        nonlocal fetched
        async with semaphore:
            df = await asyncio.to_thread(_fetch_history_sync, code, "daily", days)
            if df is not None and not df.empty:
                await save_history_to_db(code, df)
                # 同时加载到内存缓存
                from backend.utils.cache import history_cache
                column_mapping = {
                    "日期": "trade_date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume",
                    "成交额": "amount", "振幅": "amplitude",
                    "涨跌幅": "change_pct", "涨跌额": "change_amt",
                    "换手率": "turnover_rate",
                }
                df_renamed = df.rename(columns=column_mapping)
                history_cache[code] = df_renamed
                fetched += 1
                return 1
            return 0

    tasks = [fetch_and_save(code) for code in missing_codes]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success = sum(r for r in results if isinstance(r, int))
    logger.info(f"历史数据种子完成: {success}/{len(missing_codes)} 只 (新获取)")
    return success
