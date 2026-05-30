"""
REST API路由
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text

from backend.database import async_session
from backend.api.schemas import HealthResponse, StockDetail, NewsItem, PaginatedResponse
from backend.scoring.engine import get_top_rankings
from backend.utils.trading_calendar import get_market_status
from backend.utils.cache import history_cache

CST = ZoneInfo("Asia/Shanghai")
START_TIME = time.time()

router = APIRouter(prefix="/api", tags=["API"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """系统健康检查"""
    status = get_market_status()

    async with async_session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM stock_realtime"))
        count = result.scalar() or 0

        last_result = await session.execute(
            text("SELECT updated_at FROM system_state WHERE key = 'last_realtime_update'")
        )
        last_row = last_result.fetchone()

    return HealthResponse(
        status="ok",
        trading=status,
        last_update=last_row[0] if last_row else None,
        stocks_tracked=count,
        uptime_seconds=round(time.time() - START_TIME, 1),
    )


@router.get("/ranking")
async def get_ranking(
    limit: int = Query(default=50, ge=1, le=100),
    sort_by: str = Query(default="composite_score"),
):
    """获取Top股票排名"""
    rankings = await get_top_rankings(limit=limit)

    # 按指定字段排序
    if sort_by in ["composite_score", "technical_score", "sentiment_score",
                    "fund_flow_score", "momentum_score", "volume_score",
                    "change_pct", "latest_price"]:
        reverse = sort_by not in ["code", "rank"]
        rankings.sort(key=lambda x: x.get(sort_by, 0) or 0, reverse=reverse)

    return {"items": rankings, "total": len(rankings), "updated_at": datetime.now(CST).isoformat()}


@router.get("/stocks/{code}")
async def get_stock_detail(code: str):
    """获取个股详情"""
    async with async_session() as session:
        # 实时行情
        rt = await session.execute(
            text("SELECT * FROM stock_realtime WHERE code = :code"),
            {"code": code}
        )
        rt_row = rt.fetchone()
        if not rt_row:
            raise HTTPException(status_code=404, detail="股票代码不存在")

        rt_dict = dict(rt_row._mapping)

        # 技术指标
        ind = await session.execute(
            text("SELECT * FROM technical_indicators WHERE code = :code"),
            {"code": code}
        )
        ind_row = ind.fetchone()
        indicators = dict(ind_row._mapping) if ind_row else {}

        # 评分
        scores = await session.execute(
            text("SELECT * FROM stock_scores WHERE code = :code"),
            {"code": code}
        )
        score_row = scores.fetchone()
        score_dict = dict(score_row._mapping) if score_row else {}

        # 新闻
        news = await session.execute(
            text("""
                SELECT id, title, content, source, publish_time,
                       sentiment_score, sentiment_label
                FROM news_articles
                WHERE code = :code
                ORDER BY publish_time DESC
                LIMIT 20
            """),
            {"code": code}
        )
        news_list = [dict(row._mapping) for row in news.fetchall()]

    return {
        **rt_dict,
        "indicators": _clean_indicators(indicators),
        "scores": score_dict,
        "news": news_list,
    }


@router.get("/stocks/{code}/history")
async def get_stock_history(
    code: str,
    days: int = Query(default=60, ge=1, le=365),
):
    """获取股票历史K线"""
    # 先从缓存获取
    df = history_cache.get(code)
    if df is not None:
        data = df.tail(days).to_dict(orient="records")
        return {"code": code, "count": len(data), "data": data}

    # 从数据库获取
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT trade_date, open, high, low, close, volume, amount,
                       change_pct, turnover_rate
                FROM stock_daily
                WHERE code = :code
                ORDER BY trade_date DESC
                LIMIT :days
            """),
            {"code": code, "days": days}
        )
        rows = result.fetchall()
        data = [dict(row._mapping) for row in rows]
        data.reverse()  # 升序

    return {"code": code, "count": len(data), "data": data}


@router.get("/stocks/{code}/news")
async def get_stock_news(
    code: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """获取股票相关新闻"""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT id, code, title, content, source, url, publish_time,
                       sentiment_score, sentiment_label
                FROM news_articles
                WHERE code = :code
                ORDER BY publish_time DESC
                LIMIT :limit
            """),
            {"code": code, "limit": limit}
        )
        news = [dict(row._mapping) for row in result.fetchall()]

    return {"code": code, "count": len(news), "items": news}


@router.get("/stocks/{code}/indicators")
async def get_stock_indicators(code: str):
    """获取股票技术指标"""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT * FROM technical_indicators WHERE code = :code"),
            {"code": code}
        )
        row = result.fetchone()
        if not row:
            return {"code": code, "indicators": None, "message": "暂无指标数据"}

    indicators = dict(row._mapping)
    return {"code": code, "indicators": _clean_indicators(indicators)}


@router.get("/fund-flow")
async def get_fund_flow_ranking():
    """获取资金流向排名"""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT f.code, f.flow_date, f.main_net_inflow, f.main_net_pct,
                       f.super_large_inflow, f.large_inflow,
                       r.name, r.latest_price, r.change_pct
                FROM fund_flow f
                JOIN stock_realtime r ON f.code = r.code
                WHERE f.main_net_pct IS NOT NULL
                ORDER BY f.main_net_pct DESC
                LIMIT 50
            """)
        )
        items = [dict(row._mapping) for row in result.fetchall()]

    return {"items": items, "total": len(items)}


@router.get("/search")
async def search_stock(q: str = Query(min_length=1)):
    """搜索股票（按名称或代码）"""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT r.code, r.name, r.latest_price, r.change_pct,
                       r.pe_ttm, r.total_mv
                FROM stock_realtime r
                WHERE r.code LIKE :query OR r.name LIKE :query
                LIMIT 20
            """),
            {"query": f"%{q}%"}
        )
        items = [dict(row._mapping) for row in result.fetchall()]

    return {"query": q, "count": len(items), "items": items}


def _clean_indicators(ind: dict) -> dict:
    """清理指标数据，移除SQLAlchemy内部字段"""
    skip_keys = {"_sa_instance_state", "computed_at"}
    result = {}
    for k, v in ind.items():
        if k not in skip_keys:
            result[k] = round(v, 4) if isinstance(v, float) else v
    return result
