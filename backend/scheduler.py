"""
任务调度器 - APScheduler配置
管理实时数据采集、分析、评分的定时执行
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from loguru import logger

from backend.config import (
    REALTIME_INTERVAL_SEC, NEWS_INTERVAL_SEC, IDLE_INTERVAL_SEC,
    CANDIDATE_COUNT,
)
from backend.database import async_session
from backend.collectors.realtime import (
    fetch_realtime_data, save_realtime_to_db, get_candidate_codes
)
from backend.collectors.fund_flow import fetch_fund_flow, save_fund_flow_to_db
from backend.collectors.news import fetch_news_batch, save_news_to_db
from backend.analyzers.sentiment import analyze_news_batch
from backend.scoring.engine import run_scoring_pipeline, get_top_rankings
from backend.api.websocket import ws_manager
from backend.utils.trading_calendar import is_trading_time, get_market_status

CST = ZoneInfo("Asia/Shanghai")

# 全局调度器
scheduler = AsyncIOScheduler(timezone=CST)


def _now_str() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


async def _run_realtime_cycle():
    """
    实时数据循环 (60秒一次)
    1. 获取全A股实时行情
    2. 筛选候选股
    3. 补充历史数据（首次）
    4. 计算技术指标
    5. 运行评分
    6. WebSocket推送排名
    """
    try:
        is_trading = is_trading_time()

        # Step 1: 获取实时行情
        df = await fetch_realtime_data()
        if df is None or df.empty:
            logger.warning("实时行情数据为空，跳过本轮")
            return

        await save_realtime_to_db(df)

        # 更新系统状态
        async with async_session() as session:
            await session.execute(
                text("""
                    INSERT OR REPLACE INTO system_state (key, value, updated_at)
                    VALUES ('last_realtime_update', :now, :now)
                """),
                {"now": _now_str()}
            )
            await session.commit()

        # Step 2: 筛选候选股
        candidate_codes = await get_candidate_codes(CANDIDATE_COUNT)
        logger.debug(f"候选股: {len(candidate_codes)} 只")

        # Step 2.5: 检查并补充历史数据（首次启动时关键！）
        from backend.collectors.historical import seed_history_for_codes, load_history_to_cache
        from backend.utils.cache import history_cache

        # 加载已有的历史数据到缓存
        new_codes = [c for c in candidate_codes if c not in history_cache]
        if new_codes:
            await load_history_to_cache(new_codes)

        # 如果候选股还没有历史数据，增量获取
        still_missing = [c for c in candidate_codes if c not in history_cache]
        if still_missing:
            logger.info(f"候选股中 {len(still_missing)} 只缺少历史数据，开始补充...")
            # 分批获取，避免一次性请求太多
            batch_size = 5
            for i in range(0, min(len(still_missing), 20), batch_size):
                batch = still_missing[i:i + batch_size]
                await seed_history_for_codes(batch, max_concurrent=3, days=60)

        # Step 3-4: 运行评分（交易时段和非交易时段都运行）
        rankings = await run_scoring_pipeline(candidate_codes)

        # Step 5: WebSocket推送
        if rankings:
            await ws_manager.broadcast_ranking(rankings)

        if is_trading:
            # 交易时段：检查是否有值得关注的告警
            for stock in rankings[:5]:
                if stock["composite_score"] >= 75:
                    await ws_manager.send_alert(
                        level="info",
                        message=f"[ALERT] {stock['name']}({stock['code']}) score={stock['composite_score']:.1f}, "
                                f"信号: {stock['technical_signal']}，涨跌幅: {stock['change_pct']:+.2f}%",
                        code=stock["code"],
                    )

        status = get_market_status()
        logger.info(f"实时周期完成: {len(rankings)} 只已排名 (市场状态: {status})")

    except Exception as e:
        logger.error(f"实时数据循环异常: {e}", exc_info=True)


async def _run_news_cycle():
    """
    新闻更新循环 (30分钟一次)
    1. 获取候选股新闻
    2. 保存新闻
    3. 分析情绪
    """
    try:
        candidate_codes = await get_candidate_codes(CANDIDATE_COUNT)

        # 获取新闻
        news_data = await fetch_news_batch(candidate_codes[:50])  # 限制数量
        for code, news_list in news_data.items():
            await save_news_to_db(code, news_list)

        # 分析情绪
        await analyze_news_batch()

        logger.info(f"新闻更新完成: {sum(len(v) for v in news_data.values())} 篇")

    except Exception as e:
        logger.error(f"新闻更新循环异常: {e}")


async def _run_fund_flow_cycle():
    """资金流向更新循环 (每5分钟)"""
    try:
        df = await fetch_fund_flow()
        if df is not None and not df.empty:
            await save_fund_flow_to_db(df)
            logger.debug("资金流向更新完成")
    except Exception as e:
        logger.error(f"资金流向更新异常: {e}")


async def _run_eod_sync():
    """收盘后同步日K线 (15:05)"""
    try:
        from backend.collectors.historical import fetch_all_history, save_history_to_db

        async with async_session() as session:
            result = await session.execute(text("SELECT code FROM stocks WHERE is_active = 1"))
            codes = [row[0] for row in result.fetchall()]

        history_data = await fetch_all_history(codes)
        for code, df in history_data.items():
            await save_history_to_db(code, df)

        logger.info(f"盘后历史同步完成: {len(history_data)} 只")
    except Exception as e:
        logger.error(f"盘后同步异常: {e}")


async def _run_ai_analysis_cycle():
    """
    AI分析循环 (每5分钟)
    1. 生成市场总结
    2. 对Top股票做深度AI分析
    3. 异常检测
    """
    from backend.config import AI_STOCK_ANALYSIS_COUNT
    from backend.ai.analyst import generate_market_summary, detect_anomalies
    from backend.ai.news_sentiment import batch_ai_sentiment
    from backend.scoring.engine import get_top_rankings
    from backend.api.websocket import ws_manager

    try:
        rankings = await get_top_rankings(limit=50)
        if not rankings:
            return

        status = get_market_status()

        # 市场总结
        summary_data = [{
            'code': r['code'], 'name': r['name'],
            'composite_score': r['composite_score'], 'technical_score': r['technical_score'],
            'change_pct': r['change_pct'], 'technical_signal': r['technical_signal']
        } for r in rankings]

        await generate_market_summary(summary_data, status)

        # 异常检测
        anomalies = await detect_anomalies(summary_data)
        if anomalies:
            for a in anomalies[:3]:
                await ws_manager.send_alert(
                    level="info",
                    message=f"[AI检测] {a.get('alert', '')}",
                    code=a.get('code', ''),
                )

        # 对Top10股票做AI新闻情绪分析
        top_codes = [r['code'] for r in rankings[:AI_STOCK_ANALYSIS_COUNT]]
        await batch_ai_sentiment(top_codes)

        logger.info(f"AI分析周期完成: 异常{len(anomalies)}个, 情绪分析{len(top_codes)}只")

    except Exception as e:
        logger.error(f"AI分析循环异常: {e}")


def setup_scheduler():
    """配置并启动调度器"""

    # Job 1: 实时行情 + 评分 (每5秒)
    scheduler.add_job(
        _run_realtime_cycle,
        IntervalTrigger(seconds=REALTIME_INTERVAL_SEC),
        id="realtime_cycle",
        name="实时行情与评分",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=10,
    )

    # Job 2: 资金流向 (每5分钟)
    scheduler.add_job(
        _run_fund_flow_cycle,
        IntervalTrigger(minutes=5),
        id="fund_flow_cycle",
        name="资金流向更新",
        max_instances=1,
        coalesce=True,
    )

    # Job 3: 新闻更新 (每30分钟)
    scheduler.add_job(
        _run_news_cycle,
        IntervalTrigger(minutes=30),
        id="news_cycle",
        name="新闻与情绪分析",
        max_instances=1,
        coalesce=True,
    )

    # Job 4: 盘后历史同步 (15:05, 周一至周五)
    scheduler.add_job(
        _run_eod_sync,
        CronTrigger(hour=15, minute=5, day_of_week="mon-fri"),
        id="eod_sync",
        name="盘后K线同步",
        max_instances=1,
    )

    # Job 5: AI分析 (每5分钟, 如果启用)
    from backend.config import AI_ANALYSIS_ENABLED
    if AI_ANALYSIS_ENABLED:
        scheduler.add_job(
            _run_ai_analysis_cycle,
            IntervalTrigger(minutes=5),
            id="ai_analysis_cycle",
            name="AI分析与异常检测",
            max_instances=1,
            coalesce=True,
        )
        logger.info("  AI分析: 已启用 (每5分钟)")

    # 启动
    scheduler.start()
    logger.info("Scheduler started")

    # 打印各任务
    for job in scheduler.get_jobs():
        logger.info(f"  任务: {job.name} (ID: {job.id}) | 下次运行: {job.next_run_time}")

    return scheduler


def shutdown_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("调度器已关闭")
