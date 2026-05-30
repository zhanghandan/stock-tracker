"""
TTL内存缓存
"""
import time
import threading
from typing import Any, Callable


class TTLCache:
    """带过期时间的内存缓存"""

    def __init__(self, ttl_seconds: float = 300):
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """获取缓存值，过期返回None"""
        with self._lock:
            if key in self._data:
                ts, val = self._data[key]
                if time.time() - ts < self._ttl:
                    return val
                else:
                    del self._data[key]
        return None

    def set(self, key: str, value: Any):
        """设置缓存值"""
        with self._lock:
            self._data[key] = (time.time(), value)

    def delete(self, key: str):
        """删除缓存"""
        with self._lock:
            self._data.pop(key, None)

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._data.clear()

    def cleanup(self):
        """清理过期数据"""
        now = time.time()
        with self._lock:
            expired = [k for k, (ts, _) in self._data.items() if now - ts >= self._ttl]
            for k in expired:
                del self._data[k]

    def __len__(self) -> int:
        return len(self._data)


# 全局缓存实例
realtime_cache = TTLCache(ttl_seconds=10)       # 实时行情 10秒
fund_flow_cache = TTLCache(ttl_seconds=300)      # 资金流向 5分钟
news_cache = TTLCache(ttl_seconds=1800)          # 新闻 30分钟
history_cache: dict[str, Any] = {}               # 历史K线常驻内存


def cached(ttl: float = 300):
    """装饰器：缓存函数返回值"""
    def decorator(func: Callable):
        cache_store = {}

        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            now = time.time()
            if key in cache_store:
                ts, val = cache_store[key]
                if now - ts < ttl:
                    return val
            result = func(*args, **kwargs)
            cache_store[key] = (now, result)
            return result

        return wrapper
    return decorator
