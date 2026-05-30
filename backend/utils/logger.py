"""
结构化日志配置
"""
import sys
from loguru import logger
from backend.config import LOG_DIR, LOG_LEVEL, LOG_FORMAT


def setup_logger(name: str = "stock_tracker") -> logger:
    """配置并返回logger实例"""
    # 移除默认handler
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stdout,
        format=LOG_FORMAT,
        level=LOG_LEVEL,
        colorize=True,
    )

    # 文件输出 (按天轮转)
    logger.add(
        LOG_DIR / "tracker_{time:YYYY-MM-DD}.log",
        format=LOG_FORMAT,
        level=LOG_LEVEL,
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
    )

    # 错误文件单独记录
    logger.add(
        LOG_DIR / "error_{time:YYYY-MM-DD}.log",
        format=LOG_FORMAT,
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        encoding="utf-8",
    )

    return logger.bind(name=name)
