"""
AI分析结果缓存 - TTL过期 + 持久化到DB
避免重复调用DeepSeek API，节省费用
"""
import time
import json
import threading
from loguru import logger
from sqlalchemy import text


class AIResultCache:
    """AI分析结果缓存"""

    def __init__(self):
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl: int = 300) -> dict | None:
        """获取缓存，ttl秒内有效"""
        with self._lock:
            if key in self._cache:
                ts, val = self._cache[key]
                if time.time() - ts < ttl:
                    return val
                del self._cache[key]
        return None

    def set(self, key: str, value: dict):
        """写入缓存"""
        with self._lock:
            self._cache[key] = (time.time(), value)

    def clear(self):
        with self._lock:
            self._cache.clear()

    def __len__(self):
        return len(self._cache)


# 全局AI缓存实例
ai_cache = AIResultCache()

# 缓存TTL配置（秒）
CACHE_TTL = {
    "market_summary": 300,      # 5分钟
    "stock_analysis": 1800,     # 30分钟
    "news_sentiment": 3600,     # 1小时
    "anomaly_detect": 300,     # 5分钟
}
