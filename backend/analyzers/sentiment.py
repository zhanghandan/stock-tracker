"""
新闻情绪分析器 - 使用SnowNLP进行中文情绪分析
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from loguru import logger

from backend.database import async_session
from backend.collectors.news import get_unanalyzed_news, update_news_sentiment

CST = ZoneInfo("Asia/Shanghai")


def analyze_sentiment(text: str) -> tuple[float, str]:
    """
    分析文本情绪
    返回: (score: -1~1, label: 'positive'|'negative'|'neutral')
    """
    if not text or len(text.strip()) < 5:
        return 0.0, "neutral"

    try:
        from snownlp import SnowNLP
        s = SnowNLP(text)
        raw_score = s.sentiments  # 0~1, 越接近1越正面

        # 映射到 -1 ~ 1
        mapped_score = raw_score * 2 - 1

        # 分类标签
        if mapped_score > 0.2:
            label = "positive"
        elif mapped_score < -0.2:
            label = "negative"
        else:
            label = "neutral"

        return round(mapped_score, 4), label

    except Exception as e:
        logger.debug(f"SnowNLP分析失败: {e}")
        return 0.0, "neutral"


async def analyze_news_batch():
    """
    批量分析未处理新闻的情绪
    """
    articles = await get_unanalyzed_news(limit=500)
    if not articles:
        logger.debug("没有待分析的新闻")
        return

    semaphore = asyncio.Semaphore(20)  # 并发控制

    async def analyze_one(article: dict):
        async with semaphore:
            text = f"{article.get('title', '')} {article.get('content', '')}"[:2000]
            score, label = await asyncio.to_thread(analyze_sentiment, text)
            await update_news_sentiment(article["id"], score, label)
            return score, label

    tasks = [analyze_one(a) for a in articles]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    positive = sum(1 for r in results if not isinstance(r, Exception) and r[1] == "positive")
    negative = sum(1 for r in results if not isinstance(r, Exception) and r[1] == "negative")
    neutral = sum(1 for r in results if not isinstance(r, Exception) and r[1] == "neutral")

    logger.info(f"新闻情绪分析完成: {len(articles)} 条 (正面:{positive} 负面:{negative} 中性:{neutral})")


async def get_stock_sentiment(code: str) -> dict:
    """
    获取单只股票的综合情绪评分
    返回: {score: 0-100, avg_score: float, article_count: int, latest_trend: str}
    """
    async with async_session() as session:
        # 获取最近30天的新闻
        result = await session.execute(
            text("""
                SELECT sentiment_score, sentiment_label, publish_time
                FROM news_articles
                WHERE code = :code
                ORDER BY publish_time DESC
                LIMIT 20
            """),
            {"code": code}
        )
        rows = result.fetchall()

        if not rows:
            return {"score": 50.0, "avg_score": 0.0, "article_count": 0, "latest_trend": "neutral"}

        scores = [r[0] for r in rows if r[0] is not None]
        if not scores:
            return {"score": 50.0, "avg_score": 0.0, "article_count": len(rows), "latest_trend": "neutral"}

        # 平均情绪
        avg_score = sum(scores) / len(scores)

        # 近期情绪（最近5条加权更高）
        recent_scores = scores[:5] if len(scores) >= 5 else scores
        recent_avg = sum(recent_scores) / len(recent_scores)

        # 综合: 60%近期 + 40%全部
        combined = recent_avg * 0.6 + avg_score * 0.4

        # 映射到 0-100
        normalized = (combined + 1) * 50
        normalized = max(0.0, min(100.0, normalized))

        # 趋势判断
        if combined > 0.3:
            trend = "bullish"
        elif combined < -0.3:
            trend = "bearish"
        else:
            trend = "neutral"

        return {
            "score": round(normalized, 2),
            "avg_score": round(avg_score, 4),
            "article_count": len(rows),
            "latest_trend": trend,
        }
