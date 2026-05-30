"""
新闻采集器 - 爬取个股相关新闻
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from loguru import logger

from backend.database import async_session
from backend.collectors.base import sync_with_retry
from backend.utils.cache import news_cache

CST = ZoneInfo("Asia/Shanghai")


@sync_with_retry()
def _fetch_news_for_stock_sync(code: str) -> list[dict]:
    """同步获取单只股票的新闻"""
    import akshare as ak
    try:
        df = ak.stock_news_em(symbol=code)
        if df is not None and not df.empty:
            news_list = []
            for _, row in df.head(20).iterrows():
                news_list.append({
                    "title": str(row.get("新闻标题", row.get("title", ""))),
                    "content": str(row.get("新闻内容", row.get("content", ""))),
                    "source": str(row.get("文章来源", row.get("source", ""))),
                    "url": str(row.get("新闻链接", row.get("url", ""))),
                    "publish_time": str(row.get("发布时间", row.get("publish_time", ""))),
                })
            return news_list
        return []
    except Exception as e:
        logger.debug(f"获取 {code} 新闻失败: {e}")
        return []


async def fetch_news_batch(codes: list[str]) -> dict[str, list[dict]]:
    """
    批量获取股票新闻
    带缓存和限流
    """
    results = {}
    semaphore = asyncio.Semaphore(5)  # 控制并发

    async def fetch_one(code: str):
        # 检查缓存
        cached = news_cache.get(f"news_{code}")
        if cached is not None:
            return code, cached

        async with semaphore:
            await asyncio.sleep(0.5)  # 限流间隔
            news_list = await asyncio.to_thread(_fetch_news_for_stock_sync, code)
            if news_list:
                news_cache.set(f"news_{code}", news_list)
            return code, news_list

    tasks = [fetch_one(code) for code in codes]
    completed = await asyncio.gather(*tasks, return_exceptions=True)

    for result in completed:
        if isinstance(result, Exception):
            logger.debug(f"获取新闻异常: {result}")
            continue
        code, news_list = result
        if news_list:
            results[code] = news_list

    logger.info(f"新闻获取完成: {len(results)}/{len(codes)} 只股票")
    return results


async def save_news_to_db(code: str, news_list: list[dict]):
    """保存新闻到数据库（去重）"""
    if not news_list:
        return

    now_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

    async with async_session() as session:
        count = 0
        for article in news_list:
            try:
                title = article.get("title", "")
                if not title:
                    continue

                # 检查是否已存在（按标题和code去重）
                existing = await session.execute(
                    text("SELECT id FROM news_articles WHERE code = :code AND title = :title"),
                    {"code": code, "title": title}
                )
                if existing.fetchone():
                    continue

                await session.execute(
                    text("""
                        INSERT INTO news_articles (
                            code, title, content, source, url,
                            publish_time, sentiment_score, sentiment_label, fetched_at
                        ) VALUES (
                            :code, :title, :content, :source, :url,
                            :publish_time, :sentiment_score, :sentiment_label, :fetched_at
                        )
                    """),
                    {
                        "code": code,
                        "title": title,
                        "content": article.get("content", ""),
                        "source": article.get("source", ""),
                        "url": article.get("url", ""),
                        "publish_time": article.get("publish_time", ""),
                        "sentiment_score": 0.0,  # 后续由sentiment分析器填充
                        "sentiment_label": "neutral",
                        "fetched_at": now_str,
                    }
                )
                count += 1
            except Exception as e:
                logger.debug(f"保存新闻失败 {code}: {e}")
                continue

        await session.commit()
    if count > 0:
        logger.debug(f"新闻保存完成 {code}: {count} 条新文章")


async def get_unanalyzed_news(limit: int = 500) -> list[dict]:
    """获取尚未进行情绪分析的新闻"""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT id, code, title, content
                FROM news_articles
                WHERE sentiment_label = 'neutral' AND sentiment_score = 0.0
                LIMIT :limit
            """),
            {"limit": limit}
        )
        rows = result.fetchall()
        return [
            {"id": row[0], "code": row[1], "title": row[2], "content": row[3]}
            for row in rows
        ]


async def update_news_sentiment(article_id: int, score: float, label: str):
    """更新新闻情绪分析结果"""
    async with async_session() as session:
        await session.execute(
            text("""
                UPDATE news_articles
                SET sentiment_score = :score, sentiment_label = :label
                WHERE id = :id
            """),
            {"id": article_id, "score": score, "label": label}
        )
        await session.commit()
