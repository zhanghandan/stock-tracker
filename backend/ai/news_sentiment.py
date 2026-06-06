"""
DeepSeek AI 新闻情绪分析
替代SnowNLP，用于Top20高分股的精��新闻解读
"""
import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from loguru import logger

from backend.database import async_session
from backend.ai.client import get_deepseek_client, DEEPSEEK_MODEL
from backend.ai.analyst import _call_deepseek
from backend.ai.cache import ai_cache, CACHE_TTL

CST = ZoneInfo("Asia/Shanghai")


async def analyze_news_with_ai(code: str, news_list: list[dict]) -> dict:
    """
    使用DeepSeek深度分析个股新闻情绪
    输入: 股票代码 + 最近新闻列表
    输出: 情绪评分(0-100) + AI分析摘要
    """
    if not news_list:
        return {"score": 50.0, "label": "neutral", "summary": "暂无新闻"}

    cache_key = f"news_sentiment:{code}"
    cached = ai_cache.get(cache_key, CACHE_TTL["news_sentiment"])
    if cached:
        return cached

    try:
        # 整理新闻标题
        news_text = "\n".join([
            f"[{n.get('publish_time', '?')}] {n.get('title', '无标题')}"
            for n in news_list[:10]  # 最多10条
        ])

        prompt = f"""分析以下A股个股新闻，判断整体情绪倾向。

股票: {code}
最近新闻���题列表:
{news_text}

请以JSON格式返回：
{{
  "score": 数值(0=极度利空, 100=极度利好, 50=中性),
  "label": "positive/neutral/negative",
  "summary": "一句话总结新闻面情绪(20字以内)",
  "key_factors": ["关键利多因素1", "关键利空因素1"]
}}"""

        result_text = _call_deepseek(
            "你是专业的金融新闻分析师。只返回JSON，不要其他内容。",
            prompt,
            max_tokens=300,
            temperature=0.1
        )

        # 解析JSON
        try:
            # 清理可能的markdown代码块
            result_text = result_text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # 解析失败，使用SnowNLP fallback
            result = _fallback_sentiment(news_list)

        ai_cache.set(cache_key, result)
        return result

    except Exception as e:
        logger.debug(f"AI新闻分析失败 {code}: {e}")
        return _fallback_sentiment(news_list)


def _fallback_sentiment(news_list: list[dict]) -> dict:
    """SnowNLP降级方案"""
    try:
        from snownlp import SnowNLP
        scores = []
        for n in news_list[:5]:
            text = (n.get("title", "") + " " + (n.get("content", "") or ""))[:500]
            if text.strip():
                scores.append(SnowNLP(text).sentiments)
        if scores:
            avg = sum(scores) / len(scores)
            mapped = avg * 100
            label = "positive" if mapped > 55 else "negative" if mapped < 45 else "neutral"
            return {"score": round(mapped, 1), "label": label, "summary": f"基于{len(scores)}条新闻的SnowNLP分析"}
    except Exception:
        pass
    return {"score": 50.0, "label": "neutral", "summary": "无法分析"}


async def batch_ai_sentiment(codes: list[str], limit: int = 20) -> dict[str, dict]:
    """
    批量AI新闻情绪分析（仅Top20股票）
    每批5只并发
    """
    results = {}
    semaphore = asyncio.Semaphore(5)

    async def analyze_one(code: str):
        async with semaphore:
            async with async_session() as session:
                result = await session.execute(
                    text("""
                        SELECT title, content, publish_time
                        FROM news_articles
                        WHERE code = :code
                        ORDER BY publish_time DESC
                        LIMIT 10
                    """),
                    {"code": code}
                )
                news_list = [dict(row._mapping) for row in result.fetchall()]

            if news_list:
                sentiment = await analyze_news_with_ai(code, news_list)
                results[code] = sentiment
            else:
                results[code] = {"score": 50.0, "label": "neutral", "summary": "无新闻"}

    tasks = [analyze_one(code) for code in codes[:limit]]
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(f"AI新闻情绪批量分析完成: {len(results)} 只")
    return results
