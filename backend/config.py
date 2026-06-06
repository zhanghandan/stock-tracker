"""
A股高价值股实时追踪系统 - 配置文件
"""
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"

# 云端部署：支持环境变量覆盖
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT_DIR / "data")))
LOG_DIR = Path(os.getenv("LOG_DIR", str(ROOT_DIR / "logs")))
SERVER_PORT = int(os.getenv("PORT", "8000"))

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 数据库
DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'stock_tracker.db'}"

# A股交易时段 (Asia/Shanghai)
TRADING_MORNING_START = (9, 30)   # 9:30
TRADING_MORNING_END = (11, 30)    # 11:30
TRADING_AFTERNOON_START = (13, 0) # 13:00
TRADING_AFTERNOON_END = (15, 0)   # 15:00

# 实时数据刷新间隔 (秒)
# 新浪API获取全量数据需15-30秒，交易时段60秒间隔，非交易时段5分钟
REALTIME_INTERVAL_SEC = 60
# 新闻刷新间隔 (秒)
NEWS_INTERVAL_SEC = 1800  # 30分钟
# 非交易时段刷新间隔 (秒)
IDLE_INTERVAL_SEC = 300   # 5分钟

# 候选股数量 (从全量中筛选用于深度分析)
CANDIDATE_COUNT = 200

# 历史数据天数
HISTORY_DAYS = 60

# 评分权重
SCORING_WEIGHTS = {
    "technical": 0.35,
    "sentiment": 0.20,
    "fund_flow": 0.20,
    "momentum": 0.15,
    "volume": 0.10,
}

# 排除条件
EXCLUDE_ST_STOCKS = True
EXCLUDE_PRICE_BELOW = 2.0          # 排除2元以下股票
EXCLUDE_PE_ABOVE = 500             # PE>500扣分
PE_NEGATIVE_PENALTY = -10          # PE为负扣分

# 买卖信号阈值
SIGNAL_THRESHOLDS = {
    "STRONG_BUY": 75,
    "BUY": 65,
    "HOLD": 45,
    "WEAK_HOLD": 30,
    # <30 = SELL
}

# WebSocket配置
WS_MAX_CONNECTIONS = 100
WS_PING_INTERVAL = 30  # 秒

# API限流
API_RETRY_COUNT = 3
API_RETRY_DELAY = 2.0  # 秒
API_TIMEOUT = 30       # 秒

# 前端静态文件 (生产模式)
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

# DeepSeek AI配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 如果环境变量未设置，尝试从文件读取
if not DEEPSEEK_API_KEY:
    _key_file = Path(__file__).parent.parent / ".deepseek_key"
    if _key_file.exists():
        DEEPSEEK_API_KEY = _key_file.read_text().strip()

# AI分析配置
AI_ANALYSIS_ENABLED = bool(DEEPSEEK_API_KEY)
AI_MARKET_SUMMARY_INTERVAL = 300    # 市场总结刷新间隔(秒)
AI_STOCK_ANALYSIS_COUNT = 10        # 每次深度分析Top N只
AI_ANOMALY_CHECK_INTERVAL = 300     # 异常检测间隔(秒)

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}"
