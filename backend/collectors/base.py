"""
数据采集基类 - 重试、限流、异常处理
"""
import asyncio
import time
from functools import wraps
from loguru import logger
from backend.config import API_RETRY_COUNT, API_RETRY_DELAY, API_TIMEOUT


def with_retry(retries: int = API_RETRY_COUNT, delay: float = API_RETRY_DELAY):
    """异步重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    last_error = e
                    if attempt < retries - 1:
                        wait = delay * (2 ** attempt)
                        logger.warning(
                            f"{func.__name__} 第{attempt+1}次失败: {e}, "
                            f"{wait:.1f}秒后重试..."
                        )
                        await asyncio.sleep(wait)
                    else:
                        logger.error(
                            f"{func.__name__} 重试{retries}次全部失败: {last_error}"
                        )
            raise last_error
        return wrapper
    return decorator


def sync_with_retry(retries: int = API_RETRY_COUNT, delay: float = API_RETRY_DELAY):
    """同步重试装饰器 (用于akshare同步调用)"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < retries - 1:
                        wait = delay * (2 ** attempt)
                        logger.warning(
                            f"{func.__name__} 第{attempt+1}次失败: {e}, "
                            f"{wait:.1f}秒后重试..."
                        )
                        time.sleep(wait)
                    else:
                        logger.error(
                            f"{func.__name__} 重试{retries}次全部失败: {last_error}"
                        )
            raise last_error
        return wrapper
    return decorator


class RateLimiter:
    """简易令牌桶限流器"""

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls: list[float] = []

    async def acquire(self):
        """等待直到可以发起请求"""
        now = time.time()
        # 清理过期记录
        self.calls = [t for t in self.calls if now - t < self.period]

        if len(self.calls) >= self.max_calls:
            wait = self.calls[0] + self.period - now + 0.1
            if wait > 0:
                await asyncio.sleep(wait)

        self.calls.append(time.time())
