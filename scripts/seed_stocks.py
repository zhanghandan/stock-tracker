"""
导入A股全量股票列表到数据库
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import akshare as ak
from sqlalchemy import text
from backend.database import async_session, init_db
from backend.utils.logger import setup_logger

logger = setup_logger("seed_stocks")


async def seed_stocks():
    """获取A股全量列表并写入stocks表"""
    await init_db()

    logger.info("正在从东方财富获取A股股票列表...")

    try:
        # 使用akshare获取全A股列表
        df = ak.stock_zh_a_spot_em()
        logger.info(f"获取到 {len(df)} 条股票数据")
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        # 降级方案：尝试单独获取股票信息
        try:
            df = ak.stock_info_a_code_name()
            logger.info(f"降级获取到 {len(df)} 条股票基本信息")
        except Exception as e2:
            logger.error(f"降级方案也失败了: {e2}")
            return

    async with async_session() as session:
        count = 0
        for _, row in df.iterrows():
            try:
                code = str(row.get("代码", row.get("code", "")))
                name = str(row.get("名称", row.get("name", "")))

                if not code or not name:
                    continue

                # 判断市场
                if code.startswith("6"):
                    market = "SH"
                elif code.startswith(("0", "3")):
                    market = "SZ"
                elif code.startswith(("4", "8")):
                    market = "BJ"
                else:
                    market = "OTHER"

                # 使用INSERT OR REPLACE避免重复
                await session.execute(
                    text("""
                        INSERT OR REPLACE INTO stocks (code, name, market, is_active)
                        VALUES (:code, :name, :market, 1)
                    """),
                    {"code": code, "name": name, "market": market}
                )
                count += 1

            except Exception as e:
                logger.warning(f"处理股票 {code} 时出错: {e}")
                continue

        await session.commit()
        logger.info(f"✅ 成功导入 {count} 只股票到数据库")


if __name__ == "__main__":
    asyncio.run(seed_stocks())
