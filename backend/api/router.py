"""
REST API路由
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, HTTPException, Depends, Body
from backend.auth.dependencies import get_current_user
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


# ===== Auth Endpoints =====

@router.post("/auth/send-code")
async def send_verification_code(phone: str):
    """发送短信验证码"""
    import re
    if not re.match(r'^1[3-9]\d{9}$', phone):
        raise HTTPException(status_code=400, detail="请输入正确的手机号")

    from backend.auth.sms import generate_code, send_sms, save_code_to_db

    code = generate_code()
    await save_code_to_db(phone, code)
    success = await send_sms(phone, code)

    # 开发模式：返回验证码（生产环境删除此行）
    is_dev = not success or True  # 暂时始终返回验证码，方便调试
    return {
        "success": True,
        "message": "验证码已发送" if success else "验证码生成成功（开发模式）",
        "code": code if is_dev else None,  # 生产环境不返回验证码
    }


@router.post("/auth/login")
async def login(phone: str, code: str):
    """手机号+验证码登录"""
    from backend.auth.sms import verify_code
    from backend.auth.jwt_utils import create_token
    from sqlalchemy import text
    from backend.database import async_session

    # 开发模式万能验证码
    import os
    dev_code = os.getenv("DEV_SMS_CODE", "")
    if dev_code and code == dev_code:
        pass  # 开发万能码，跳过验证
    elif not await verify_code(phone, code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    # 查找或创建用户
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, phone, nickname FROM users WHERE phone = :phone"),
            {"phone": phone}
        )
        user = result.fetchone()

        if user:
            user_id = user[0]
            nickname = user[2]
            await session.execute(
                text("UPDATE users SET last_login = datetime('now') WHERE id = :id"),
                {"id": user_id}
            )
        else:
            result = await session.execute(
                text("""
                    INSERT INTO users (phone, nickname, created_at, last_login)
                    VALUES (:phone, :nickname, datetime('now'), datetime('now'))
                """),
                {"phone": phone, "nickname": f"用户{phone[-4:]}"}
            )
            await session.commit()
            user_id = result.lastrowid
            nickname = f"用户{phone[-4:]}"

        await session.commit()

    token = create_token(phone, user_id)
    return {
        "success": True,
        "token": token,
        "user": {"phone": phone, "user_id": user_id, "nickname": nickname},
    }


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    if not user:
        return {"logged_in": False, "user": None}

    from sqlalchemy import text
    from backend.database import async_session

    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, phone, nickname, avatar, created_at, last_login FROM users WHERE id = :id"),
            {"id": user["user_id"]}
        )
        row = result.fetchone()
        if row:
            return {
                "logged_in": True,
                "user": {
                    "id": row[0], "phone": row[1], "nickname": row[2],
                    "avatar": row[3], "created_at": row[4], "last_login": row[5],
                }
            }

    return {"logged_in": False, "user": None}


@router.post("/auth/logout")
async def logout():
    """退出登录"""
    return {"success": True, "message": "已退出"}


def _clean_indicators(ind: dict) -> dict:
    """清理指标数据，移除SQLAlchemy内部字段"""
    skip_keys = {"_sa_instance_state", "computed_at"}
    result = {}
    for k, v in ind.items():
        if k not in skip_keys:
            result[k] = round(v, 4) if isinstance(v, float) else v
    return result


# ===== AI Analysis Endpoints =====

from backend.config import AI_ANALYSIS_ENABLED


@router.get("/ai/summary")
async def ai_market_summary():
    """AI生成的每日市场总结"""
    if not AI_ANALYSIS_ENABLED:
        return {"error": "AI分析未启用，请设置DEEPSEEK_API_KEY环境变量", "enabled": False}

    from backend.ai.analyst import generate_market_summary
    from backend.scoring.engine import get_top_rankings
    from backend.utils.trading_calendar import get_market_status

    rankings = await get_top_rankings(limit=50)
    status = get_market_status()

    result = await generate_market_summary(
        [{'code': r['code'], 'name': r['name'],
          'composite_score': r['composite_score'], 'technical_score': r['technical_score'],
          'change_pct': r['change_pct'], 'technical_signal': r['technical_signal']}
         for r in rankings],
        status
    )
    return {"enabled": True, **result}


@router.get("/ai/stock/{code}")
async def ai_stock_analysis(code: str):
    """AI个股深度分析"""
    if not AI_ANALYSIS_ENABLED:
        return {"error": "AI分析未启用", "enabled": False}

    from backend.ai.analyst import analyze_stock_deep
    from sqlalchemy import text
    from backend.database import async_session

    async with async_session() as session:
        result = await session.execute(
            text("SELECT * FROM stock_scores WHERE code = :code"), {"code": code}
        )
        scores_row = result.fetchone()
        scores = dict(scores_row._mapping) if scores_row else {}

        result = await session.execute(
            text("SELECT * FROM technical_indicators WHERE code = :code"), {"code": code}
        )
        ind_row = result.fetchone()
        indicators = dict(ind_row._mapping) if ind_row else {}

        result = await session.execute(
            text("SELECT name, latest_price, change_pct, pe_ttm, total_mv FROM stock_realtime WHERE code = :code"),
            {"code": code}
        )
        rt_row = result.fetchone()
        rt = dict(rt_row._mapping) if rt_row else {}

    stock_data = {**rt, "code": code, "scores": scores, "indicators": indicators}
    analysis = await analyze_stock_deep(stock_data)
    return {"enabled": True, **analysis}


@router.get("/ai/anomalies")
async def ai_anomaly_detection():
    """AI异常检测"""
    if not AI_ANALYSIS_ENABLED:
        return {"error": "AI分析未启用", "enabled": False}

    from backend.ai.analyst import detect_anomalies
    from backend.scoring.engine import get_top_rankings

    rankings = await get_top_rankings(limit=50)
    anomalies = await detect_anomalies([
        {'code': r['code'], 'name': r['name'],
         'composite_score': r['composite_score'], 'technical_score': r['technical_score'],
         'change_pct': r['change_pct'], 'technical_signal': r['technical_signal']}
        for r in rankings
    ])
    return {"enabled": True, "anomalies": anomalies, "count": len(anomalies)}


@router.get("/ai/status")
async def ai_status():
    """AI分析模块状态"""
    return {
        "enabled": AI_ANALYSIS_ENABLED,
        "model": "deepseek-chat",
        "provider": "DeepSeek (OpenAI compatible)",
        "features": ["market_summary", "stock_analysis", "anomaly_detection", "news_sentiment", "ai_chat", "ai_ranking"],
    }


@router.post("/ai/chat")
async def ai_chat_endpoint(payload: dict = Body(...)):
    """AI自由对话 - 询问股票推荐、分析优缺点等"""
    if not AI_ANALYSIS_ENABLED:
        return {"error": "AI分析未启用，请设置DEEPSEEK_API_KEY环境变量", "enabled": False}

    from backend.ai.analyst import ai_chat
    from backend.scoring.engine import get_top_rankings

    message = payload.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    chat_history = payload.get("history", [])

    rankings = await get_top_rankings(limit=30)
    context = [
        {'code': r['code'], 'name': r['name'],
         'composite_score': r['composite_score'], 'technical_score': r['technical_score'],
         'sentiment_score': r['sentiment_score'], 'fund_flow_score': r['fund_flow_score'],
         'momentum_score': r['momentum_score'], 'volume_score': r['volume_score'],
         'change_pct': r['change_pct'], 'latest_price': r['latest_price'],
         'pe_ttm': r['pe_ttm'], 'pb': r['pb'], 'total_mv': r['total_mv'],
         'technical_signal': r['technical_signal'], 'turnover_rate': r['turnover_rate']}
        for r in rankings
    ]

    result = await ai_chat(message, context, chat_history)
    return {"enabled": True, **result}


@router.post("/ai/rank")
async def ai_ranking_endpoint():
    """AI覆盖排名 - AI重新排序Top30并给出推荐理由"""
    if not AI_ANALYSIS_ENABLED:
        return {"error": "AI分析未启用", "enabled": False}

    from backend.ai.analyst import ai_rank_stocks
    from backend.scoring.engine import get_top_rankings

    rankings = await get_top_rankings(limit=30)
    context = [
        {'code': r['code'], 'name': r['name'],
         'composite_score': r['composite_score'], 'technical_score': r['technical_score'],
         'sentiment_score': r['sentiment_score'], 'fund_flow_score': r['fund_flow_score'],
         'momentum_score': r['momentum_score'], 'volume_score': r['volume_score'],
         'change_pct': r['change_pct'], 'latest_price': r['latest_price'],
         'pe_ttm': r['pe_ttm'], 'pb': r['pb'], 'total_mv': r['total_mv'],
         'technical_signal': r['technical_signal'], 'turnover_rate': r['turnover_rate']}
        for r in rankings
    ]

    ai_rankings = await ai_rank_stocks(context)
    return {"enabled": True, "rankings": ai_rankings, "count": len(ai_rankings)}


# ===== Ollama Chat Endpoints =====

@router.get("/chat/status")
async def chat_status():
    """检查聊天模块状态"""
    from backend.chat_api import check_status
    return await check_status()


@router.post("/chat/send")
async def chat_send(payload: dict = Body(...)):
    """发送消息 - 优先Ollama本地，fallback DeepSeek"""
    from backend.chat_api import chat_send

    message = payload.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    history = payload.get("history", [])
    model = payload.get("model", "")

    result = await chat_send(message, history, model)
    return result


@router.get("/chat")
async def chat_page():
    """聊天页面"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=CHAT_PAGE_HTML)


# ===== 聊骚页面 HTML =====

CHAT_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0d1117">
<title>AI Chat</title>
<style>
:root {
  --bg: #0d1117;
  --bg-card: #161b22;
  --border: #21262d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --accent: #ff6b9d;
  --accent2: #c44dff;
  --user-bg: #1f2937;
  --ai-bg: #161b22;
  --safe-bottom: env(safe-area-inset-bottom, 0px);
}
* { margin:0; padding:0; box-sizing:border-box }
html, body { height:100%; overflow:hidden }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
  -webkit-tap-highlight-color: transparent;
}
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 600px;
  margin: 0 auto;
}
/* Header */
.header {
  padding: 12px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  z-index: 10;
}
.header-title {
  font-size: 16px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.header-model {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 8px;
  background: var(--border);
  border-radius: 10px;
}
/* Messages */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  -webkit-overflow-scrolling: touch;
}
.msg {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.msg-user {
  align-self: flex-end;
  background: linear-gradient(135deg, #ff6b9d, #c44dff);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.msg-ai {
  align-self: flex-start;
  background: var(--ai-bg);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}
.msg-role {
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 4px;
}
.msg-user .msg-role { color: rgba(255,255,255,0.7) }
.msg-time {
  font-size: 9px;
  color: var(--text-muted);
  margin-top: 4px;
  text-align: right;
}
.typing {
  align-self: flex-start;
  padding: 10px 14px;
  color: var(--text-muted);
  font-size: 13px;
}
.typing-dots span {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--accent);
  margin: 0 2px;
  animation: dotBounce 1.4s infinite ease-in-out;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s }
.typing-dots span:nth-child(3) { animation-delay: 0.4s }
@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4 }
  40% { transform: scale(1); opacity: 1 }
}
/* Empty state */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 12px;
}
.empty-icon {
  font-size: 48px;
  opacity: 0.5;
}
.empty-text {
  font-size: 14px;
}
.empty-hint {
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.6;
}
/* Input */
.input-bar {
  padding: 8px 12px;
  padding-bottom: calc(8px + var(--safe-bottom));
  background: var(--bg-card);
  border-top: 1px solid var(--border);
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.input-bar textarea {
  flex: 1;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--text);
  padding: 10px 16px;
  font-size: 14px;
  resize: none;
  outline: none;
  font-family: inherit;
  max-height: 100px;
}
.input-bar textarea:focus {
  border-color: var(--accent);
}
.send-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.send-btn:disabled {
  opacity: 0.3;
}
.send-btn:active {
  transform: scale(0.9);
}
/* Quick reply tags */
.quick-replies {
  display: flex;
  gap: 6px;
  padding: 6px 12px;
  overflow-x: auto;
  flex-shrink: 0;
  scrollbar-width: none;
}
.quick-replies::-webkit-scrollbar { display:none }
.quick-tag {
  flex-shrink: 0;
  padding: 6px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.quick-tag:active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
/* Status bar */
.status-bar {
  padding: 4px 12px;
  font-size: 10px;
  color: var(--text-muted);
  text-align: center;
  flex-shrink: 0;
}
.status-bar .dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  margin-right: 4px;
}
.dot-on { background: #3fb950 }
.dot-off { background: #f85149 }
</style>
</head>
<body>
<div class="app">
  <div class="header">
    <span class="header-title">💋 AI Chat</span>
    <span class="header-model" id="modelName">loading...</span>
  </div>

  <div class="status-bar" id="statusBar">
    <span class="dot dot-off"></span> <span id="statusText">检测Ollama...</span>
  </div>

  <div class="quick-replies" id="quickReplies">
    <span class="quick-tag" onclick="sendQuick(this)">你好呀 😊</span>
    <span class="quick-tag" onclick="sendQuick(this)">陪我聊聊天</span>
    <span class="quick-tag" onclick="sendQuick(this)">讲个有意思的</span>
    <span class="quick-tag" onclick="sendQuick(this)">你觉得我怎么样</span>
    <span class="quick-tag" onclick="sendQuick(this)">夸夸我</span>
  </div>

  <div class="messages" id="messages">
    <div class="empty-state">
      <div class="empty-icon">💬</div>
      <div class="empty-text">开始聊天吧</div>
      <div class="empty-hint">本地AI · 零限制 · 绝对隐私</div>
    </div>
  </div>

  <div class="input-bar">
    <textarea id="input" rows="1" placeholder="说点什么..." onkeydown="onKeyDown(event)"></textarea>
    <button class="send-btn" onclick="sendMsg()" id="sendBtn">➤</button>
  </div>
</div>

<script>
var messages = [];
var isLoading = false;
var currentModel = '';
var msgEl = document.getElementById('messages');
var inputEl = document.getElementById('input');
var emptyState = msgEl.querySelector('.empty-state');

// Auto-resize textarea
inputEl.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 100) + 'px';
});

// Check status
fetch('/api/chat/status')
  .then(r => r.json())
  .then(d => {
    if (d.ollama_available) {
      currentModel = d.recommended || d.models[0];
      document.getElementById('modelName').textContent = currentModel;
      document.getElementById('statusBar').innerHTML = '<span class="dot dot-on"></span> <span>本地模型就绪</span>';
    } else {
      document.getElementById('modelName').textContent = '无模型';
      document.getElementById('statusBar').innerHTML = '<span class="dot dot-off"></span> <span>Ollama未安装或无模型</span>';
    }
  })
  .catch(() => {
    document.getElementById('statusBar').innerHTML = '<span class="dot dot-off"></span> <span>Ollama服务未启动</span>';
  });

function sendQuick(el) {
  sendMsg(el.textContent);
}

function onKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMsg();
  }
}

function sendMsg(text) {
  var msg = (text || inputEl.value).trim();
  if (!msg || isLoading) return;

  inputEl.value = '';
  inputEl.style.height = 'auto';
  isLoading = true;
  document.getElementById('sendBtn').disabled = true;

  // Remove empty state
  if (emptyState) {
    emptyState.remove();
    emptyState = null;
  }

  // Add user message
  addMsg('user', msg);
  messages.push({ role: 'user', content: msg });

  // Add typing indicator
  var typingEl = document.createElement('div');
  typingEl.className = 'typing';
  typingEl.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
  typingEl.id = 'typing';
  msgEl.appendChild(typingEl);
  msgEl.scrollTop = msgEl.scrollHeight;

  // Send to backend
  fetch('/api/chat/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: msg,
      history: messages.slice(0, -1),
      model: currentModel,
    }),
  })
  .then(r => r.json())
  .then(d => {
    // Remove typing
    var t = document.getElementById('typing');
    if (t) t.remove();

    var reply = d.reply || '...';
    if (d.fallback) {
      currentModel = d.model;
      document.getElementById('modelName').textContent = currentModel;
    }
    addMsg('ai', reply);
    messages.push({ role: 'assistant', content: reply });
    isLoading = false;
    document.getElementById('sendBtn').disabled = false;
    inputEl.focus();
  })
  .catch(e => {
    var t = document.getElementById('typing');
    if (t) t.remove();
    addMsg('ai', '连接失败: ' + e.message);
    isLoading = false;
    document.getElementById('sendBtn').disabled = false;
  });
}

function addMsg(role, text) {
  var div = document.createElement('div');
  div.className = 'msg ' + (role === 'user' ? 'msg-user' : 'msg-ai');
  var now = new Date().toLocaleTimeString();
  div.innerHTML = '<div class="msg-role">' + (role==='user'?'你':'AI') + '</div>'
    + '<div>' + escapeHtml(text) + '</div>'
    + '<div class="msg-time">' + now + '</div>';
  msgEl.appendChild(div);
  msgEl.scrollTop = msgEl.scrollHeight;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
}
</script>
</body>
</html>"""

