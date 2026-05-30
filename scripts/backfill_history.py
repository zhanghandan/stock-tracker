"""
回填60天历史K线数据
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.database import async_session, init_db
from backend.collectors.historical import fetch_all_history, save_history_to_db, load_history_to_cache
from backend.utils.logger import setup_logger

logger = setup_logger("backfill_history")


async def backfill():
    """回填所有股票的历史K线"""
    await init_db()

    # 1. 获取所有股票代码
    async with async_session() as session:
        result = await session.execute(
            text("SELECT code FROM stocks WHERE is_active = 1")
        )
        codes = [row[0] for row in result.fetchall()]
        logger.info(f"共 {len(codes)} 只股票需要回填历史数据")

    # 2. 分批获取历史数据
    batch_size = 200
    total_saved = 0

    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        logger.info(f"正在处理第 {i//batch_size + 1} 批 ({len(batch)} 只) ...")

        history_data = await fetch_all_history(batch)

        # 保存到数据库
        for code, df in history_data.items():
            await save_history_to_db(code, df)
            total_saved += 1

        # 显示进度
        pct = min(100, (i + batch_size) / len(codes) * 100)
        logger.info(f"进度: {total_saved}/{len(codes)} ({pct:.1f}%)")

        # 批次间休息，避免被限流
        if i + batch_size < len(codes):
            await asyncio.sleep(2)

    # 3. 加载到内存缓存
    logger.info("正在加载历史数据到内存缓存...")
    await load_history_to_cache(codes)

    logger.info(f"✅ 历史数据回填完成！共保存 {total_saved} 只股票的历史K线")


if __name__ == "__main__":
    asyncio.run(backfill())
