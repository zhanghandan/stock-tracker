"""
Pydantic请求/响应模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class StockRankingItem(BaseModel):
    """排名列表项"""
    code: str
    rank: int
    name: str
    latest_price: Optional[float] = None
    change_pct: Optional[float] = None
    composite_score: float
    technical_score: Optional[float] = None
    sentiment_score: Optional[float] = None
    fund_flow_score: Optional[float] = None
    momentum_score: Optional[float] = None
    volume_score: Optional[float] = None
    technical_signal: Optional[str] = None
    volume_ratio: Optional[float] = None
    turnover_rate: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None
    change_60d: Optional[float] = None
    scored_at: Optional[str] = None


class StockDetail(BaseModel):
    """个股详情"""
    code: str
    name: str
    latest_price: Optional[float] = None
    change_pct: Optional[float] = None
    change_amount: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prev_close: Optional[float] = None
    volume_hands: Optional[float] = None
    turnover_yuan: Optional[float] = None
    amplitude: Optional[float] = None
    volume_ratio: Optional[float] = None
    turnover_rate: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None
    float_mv: Optional[float] = None
    change_60d: Optional[float] = None
    change_ytd: Optional[float] = None
    indicators: Optional[dict] = None
    news: Optional[list[dict]] = None
    scores: Optional[dict] = None


class NewsItem(BaseModel):
    """新闻条目"""
    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    publish_time: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    trading: str
    last_update: Optional[str] = None
    stocks_tracked: int = 0
    uptime_seconds: float = 0


class PaginatedResponse(BaseModel):
    """分页响应"""
    items: list
    total: int
    page: int
    page_size: int


class WSMessage(BaseModel):
    """WebSocket消息"""
    type: str
    data: dict | list | None = None
    timestamp: Optional[str] = None
