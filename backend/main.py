"""
A股高价值股实时追踪系统 - FastAPI主入口
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend.config import FRONTEND_DIST, LOG_LEVEL, SERVER_PORT
from backend.database import init_db
from backend.api.router import router
from backend.api.websocket import ws_endpoint
from backend.scheduler import setup_scheduler, shutdown_scheduler
from backend.utils.logger import setup_logger

# 初始化日志
setup_logger("stock_tracker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 60)
    logger.info("Stock Tracker starting...")
    logger.info("=" * 60)

    # 启动时：初始化数据库
    await init_db()
    logger.info("Database initialized")

    # 自动种子数据（如果股票表为空）
    try:
        from backend.database import async_session
        from sqlalchemy import text
        async with async_session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM stocks"))
            count = result.scalar()
            if count == 0:
                logger.info("股票表为空，自动导入A股列表...")
                import akshare as ak
                df = ak.stock_zh_a_spot_em()
                for _, row in df.iterrows():
                    await session.execute(
                        text("INSERT OR IGNORE INTO stocks (code, name) VALUES (:code, :name)"),
                        {"code": str(row["代码"]), "name": str(row["名称"])}
                    )
                await session.commit()
                logger.info(f"已导入 {len(df)} 只股票")
            else:
                logger.info(f"股票表已有 {count} 条记录，跳过种子导入")
    except Exception as e:
        logger.warning(f"自动种子数据失败（可手动执行 scripts/seed_stocks.py）: {e}")

    # 启动调度器
    setup_scheduler()
    logger.info("Scheduler started (realtime tracking during trading hours)")

    yield

    # 关闭时清理
    logger.info("正在关闭系统...")
    shutdown_scheduler()
    logger.info("System shutdown complete")


# 创建FastAPI应用
app = FastAPI(
    title="A股高价值股实时追踪系统",
    description="""
    实时追踪A股市场，综合技术分析、新闻情绪、资金流向等多维度数据，
    智能评分排名，筛选出前50只最具投资价值的股票。

    ## 功能
    - **实时行情**: 每5秒刷新全A股约5000只股票行情
    - **技术分析**: MA/MACD/RSI/KDJ/Bollinger多指标综合评分
    - **新闻情绪**: 爬取个股新闻，SnowNLP中文情绪分析
    - **资金流向**: 主力资金净流入/流出追踪
    - **智能排名**: 5维度加权评分，Top50实时推送
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发模式允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API路由
app.include_router(router)

# WebSocket端点
@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """实时数据推送WebSocket"""
    await ws_endpoint(websocket)


# PWA Service Worker
@app.get("/sw.js", response_class=HTMLResponse)
async def service_worker():
    """Service Worker - 离线缓存支持"""
    from fastapi.responses import Response
    return Response(content=SW_JS, media_type="application/javascript")


# PWA Manifest
@app.get("/manifest.json")
async def manifest():
    """PWA 应用清单"""
    return MANIFEST_JSON


# Favicon
@app.get("/favicon.svg")
async def favicon():
    """网站图标"""
    from fastapi.responses import Response
    return Response(content=FAVICON_SVG, media_type="image/svg+xml")


# 生产模式：托管前端静态文件
if FRONTEND_DIST.exists() and FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
    logger.info(f"Frontend static files: {FRONTEND_DIST}")

    @app.get("/api")
    async def api_root():
        return {"message": "A股实时追踪API", "version": "1.0.0", "docs": "/api/docs"}

else:
    @app.get("/", response_class=HTMLResponse)
    async def root():
        return DASHBOARD_HTML


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<title>A股实时追踪</title>
<meta name="description" content="A股高价值股实时追踪 - 智能评分排名">
<meta name="theme-color" content="#0d1117" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="股票追踪">
<link rel="manifest" href="/manifest.json">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/favicon.svg">
<style>
:root {
  --bg: #0d1117; --bg-card: #161b22; --border: #30363d;
  --text: #c9d1d9; --text-muted: #8b949e; --accent: #58a6ff;
  --up: #ff6b6b; --down: #3fb950;
  --safe-bottom: env(safe-area-inset-bottom, 0px);
}
*{margin:0;padding:0;box-sizing:border-box}
html{height:100%}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;
  background:var(--bg);color:var(--text);min-height:100%;
  -webkit-tap-highlight-color:transparent;
  -webkit-font-smoothing:antialiased;
  padding-bottom:calc(64px + var(--safe-bottom));
  overscroll-behavior-y:contain;
}

/* === Header === */
.header{
  background:var(--bg-card);padding:10px 16px;
  border-bottom:1px solid var(--border);
  display:flex;justify-content:space-between;align-items:center;
  position:sticky;top:0;z-index:100;gap:8px;
}
.header h1{color:var(--accent);font-size:16px;white-space:nowrap}
.header-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
.status-badge{
  display:flex;align-items:center;gap:4px;font-size:11px;
  background:#21262d;padding:3px 8px;border-radius:10px;white-space:nowrap;
}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex-shrink:0}
.dot.green{background:#3fb950;box-shadow:0 0 4px #3fb950}
.dot.red{background:#f85149;box-shadow:0 0 4px #f85149}
.dot.yellow{background:#d2991d;box-shadow:0 0 4px #d2991d}
#updateTime{font-size:10px;color:var(--text-muted);display:none}

/* === Stats Row === */
.stats-row{
  display:flex;gap:8px;padding:12px 16px;overflow-x:auto;
  scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;
  scrollbar-width:none;
}
.stats-row::-webkit-scrollbar{display:none}
.stat-item{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:10px;padding:10px 14px;min-width:100px;flex-shrink:0;
  scroll-snap-align:start;text-align:center;
}
.stat-item .label{font-size:11px;color:var(--text-muted);margin-bottom:2px}
.stat-item .value{font-size:20px;font-weight:bold;color:var(--accent)}

/* === Tab Content === */
.tab-content{display:none;padding:0 12px}
.tab-content.active{display:block}

/* === Mobile Card List === */
.stock-list{display:flex;flex-direction:column;gap:8px;padding-bottom:12px}
.stock-card{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:10px;padding:12px;cursor:pointer;
  transition:background .15s;
  -webkit-tap-highlight-color:rgba(88,166,255,0.15);
}
.stock-card:active{background:#1c2129}
.stock-card .card-top{
  display:flex;justify-content:space-between;align-items:flex-start;gap:8px;
}
.stock-card .card-left{flex:1;min-width:0}
.stock-card .rank{font-size:11px;color:var(--text-muted);margin-bottom:2px}
.stock-card .name-line{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}
.stock-card .code{font-size:13px;font-weight:600;color:var(--accent)}
.stock-card .cname{font-size:14px;font-weight:500}
.stock-card .card-right{text-align:right;flex-shrink:0}
.stock-card .price{font-size:18px;font-weight:bold}
.stock-card .change{font-size:13px;font-weight:500;margin-top:1px}
.stock-card .card-mid{
  display:flex;justify-content:space-between;align-items:center;margin-top:8px;
}
.stock-card .score-wrap{display:flex;align-items:center;gap:6px}
.stock-card .score-val{font-size:22px;font-weight:bold}
.stock-card .card-detail{display:none;margin-top:10px;padding-top:10px;border-top:1px solid var(--border)}
.stock-card.expanded .card-detail{display:block}
.stock-card .detail-grid{
  display:grid;grid-template-columns:1fr 1fr;gap:6px 12px;font-size:12px;
}
.stock-card .detail-item{display:flex;justify-content:space-between}
.stock-card .detail-item .dl{color:var(--text-muted)}
.stock-card .detail-item .dv{font-weight:500}

/* Signal badges */
.badge{
  padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;
  white-space:nowrap;line-height:1.5;
}
.badge.strong_buy{background:#ff4444;color:#fff}
.badge.buy{background:#ff6b6b;color:#fff}
.badge.hold{background:#d2991d;color:#000}
.badge.weak_hold{background:#58a6ff;color:#000}
.badge.sell{background:#3fb950;color:#000}

/* === Desktop Table (>=768px) === */
.desktop-table{display:none}
@media (min-width:768px){
  .stock-list{display:none}
  .desktop-table{display:block;overflow-x:auto}
  .tab-content{padding:0 20px}
  .header{padding:12px 24px}
  .header h1{font-size:20px}
  .header-right{gap:12px}
  .status-badge{font-size:12px;padding:4px 10px}
  #updateTime{display:inline;font-size:12px}
  .stats-row{padding:16px 24px;gap:12px}
  .stat-item{padding:12px 20px;min-width:140px}
  .stat-item .value{font-size:24px}
}
table{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}
th{background:var(--bg-card);padding:10px 6px;text-align:right;border:1px solid var(--border);position:sticky;top:0;z-index:1;cursor:pointer}
th:first-child,td:first-child{text-align:center}
th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3){text-align:left}
td{padding:8px 6px;border:1px solid #21262d;text-align:right}
tr:hover{background:#1c2129}
tr:nth-child(even){background:var(--bg)}
tr:nth-child(odd){background:var(--bg-card)}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.up{color:var(--up)}
.down{color:var(--down)}
.score{font-weight:bold;font-size:15px}

/* === Search Tab === */
.search-wrap{padding:4px 0 12px}
.search-wrap input{
  width:100%;background:var(--bg);border:1px solid var(--border);
  color:var(--text);padding:12px 16px;border-radius:10px;font-size:16px;
  -webkit-appearance:none;
}
.search-wrap input:focus{outline:none;border-color:var(--accent)}
.search-results .stock-card .cname{font-size:13px}
.search-results .stock-card .code{font-size:12px}

/* === About Tab === */
.about-card{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:10px;padding:20px;text-align:center;
}
.about-card h3{color:var(--accent);margin-bottom:8px}
.about-card p{color:var(--text-muted);font-size:13px;line-height:1.6;margin:4px 0}

/* === Bottom Nav === */
.bottom-nav{
  position:fixed;bottom:0;left:0;right:0;background:var(--bg-card);
  border-top:1px solid var(--border);display:flex;z-index:200;
  padding-bottom:var(--safe-bottom);
}
.bottom-nav .nav-item{
  flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;padding:8px 4px;gap:2px;cursor:pointer;
  color:var(--text-muted);font-size:10px;transition:color .15s;
  -webkit-tap-highlight-color:rgba(88,166,255,0.15);
  min-height:52px;user-select:none;
}
.bottom-nav .nav-item.active{color:var(--accent)}
.bottom-nav .nav-item svg{width:22px;height:22px}

/* === Loading / Error === */
.loading{text-align:center;padding:60px 20px;color:var(--text-muted);font-size:15px}
.loading .spinner{
  display:inline-block;width:32px;height:32px;border:3px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin-bottom:12px;
}
@keyframes spin{to{transform:rotate(360deg)}}
.error{text-align:center;padding:60px 20px;color:#f85149}
.error small{display:block;margin-top:8px;color:var(--text-muted);font-size:12px}
.pull-hint{text-align:center;padding:8px;color:var(--text-muted);font-size:11px}

/* Toast */
.toast{
  position:fixed;top:60px;left:50%;transform:translateX(-50%);
  background:#21262d;color:var(--text);padding:10px 20px;border-radius:20px;
  font-size:13px;z-index:300;opacity:0;transition:opacity .3s;pointer-events:none;
}
.toast.show{opacity:1}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <h1>📈 股票实时追踪</h1>
  <div class="header-right">
    <span class="status-badge" id="marketBadge"><span class="dot yellow"></span> --</span>
    <span id="updateTime"></span>
  </div>
</div>

<!-- Stats -->
<div class="stats-row" id="statsRow"></div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<!-- Tab: Ranking -->
<div class="tab-content active" id="tabRanking">
  <div class="stock-list" id="stockList"></div>
  <div class="desktop-table" id="desktopTable"></div>
</div>

<!-- Tab: Search -->
<div class="tab-content" id="tabSearch">
  <div class="search-wrap">
    <input type="search" id="searchInput" placeholder="🔍 搜索股票代码或名称..." autocomplete="off">
  </div>
  <div class="stock-list search-results" id="searchResults"></div>
</div>

<!-- Tab: About -->
<div class="tab-content" id="tabAbout">
  <div class="about-card">
    <h3>📊 A股高价值股实时追踪</h3>
    <p>综合技术分析·新闻情绪·资金流向<br>多维度智能评分，实时筛选Top50</p>
    <p style="margin-top:12px;font-size:11px">
      数据来源: 东方财富/新浪/雪球<br>
      追踪股票: <strong id="aboutCount">--</strong> 只<br>
      WebSocket: <span id="aboutWS" style="color:#d2991d">未连接</span>
    </p>
    <p style="margin-top:12px;font-size:11px;color:var(--text-muted)">
      ⚠️ 本系统仅供学习研究<br>不构成任何投资建议
    </p>
  </div>
</div>

<!-- Bottom Nav -->
<div class="bottom-nav">
  <div class="nav-item active" data-tab="tabRanking" onclick="switchTab('tabRanking')">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>
    <span>排名</span>
  </div>
  <div class="nav-item" data-tab="tabSearch" onclick="switchTab('tabSearch')">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
    <span>搜索</span>
  </div>
  <div class="nav-item" data-tab="tabAbout" onclick="switchTab('tabAbout')">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
    <span>关于</span>
  </div>
</div>

<script>
// === State ===
var allStocks = [];
var ws = null;
var currentTab = 'tabRanking';

// === Tab Switching ===
function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.tab-content').forEach(function(el){el.classList.remove('active')});
  document.querySelectorAll('.nav-item').forEach(function(el){el.classList.remove('active')});
  document.getElementById(tabId).classList.add('active');
  var navItem = document.querySelector('[data-tab="'+tabId+'"]');
  if(navItem) navItem.classList.add('active');
  if(tabId === 'tabSearch') {
    document.getElementById('searchInput').focus();
    if(allStocks.length) renderSearch(allStocks);
  }
  if(tabId === 'tabAbout') updateAbout();
}

// === Toast ===
function showToast(msg) {
  var t = document.getElementById('toast');
  t.textContent = msg;t.classList.add('show');
  setTimeout(function(){t.classList.remove('show')},2000);
}

// === Fetch Rankings ===
function fetchRankings() {
  var listEl = document.getElementById('stockList');
  listEl.innerHTML = '<div class="loading"><div class="spinner"></div><br>加载排名数据...</div>';
  fetch('/api/ranking?limit=50')
    .then(function(r){return r.json()})
    .then(function(data){
      allStocks = data.items || [];
      renderAll(allStocks);
    })
    .catch(function(){
      listEl.innerHTML = '<div class="error">⚠️ 连接失败<br><small>请确认后端服务已启动</small></div>';
    });
}

// === Render All ===
function renderAll(stocks) {
  renderMobileCards(stocks);
  renderDesktopTable(stocks);
  renderStats(stocks);
  updateAbout();
}

// === Stats Row ===
function renderStats(stocks) {
  if(!stocks.length){document.getElementById('statsRow').innerHTML='';return}
  var topCount = stocks.filter(function(s){return s.composite_score >= 65}).length;
  var avgScore = (stocks.reduce(function(a,b){return a+b.composite_score},0)/stocks.length).toFixed(1);
  var top = stocks[0];
  document.getElementById('statsRow').innerHTML =
    '<div class="stat-item"><div class="label">📋 排名</div><div class="value">'+stocks.length+'</div></div>'+
    '<div class="stat-item"><div class="label">⭐ 均分</div><div class="value">'+avgScore+'</div></div>'+
    '<div class="stat-item"><div class="label">🟢 买入</div><div class="value" style="color:var(--up)">'+topCount+'</div></div>'+
    '<div class="stat-item"><div class="label">🏆 Top1</div><div class="value" style="font-size:14px">'+(top?top.code:'-')+'</div></div>';
}

// === Mobile Card View ===
function renderMobileCards(stocks) {
  var el = document.getElementById('stockList');
  if(!stocks.length){
    el.innerHTML = '<div class="loading">⏳ 等待数据...<br><small>首次启动需要约60秒采集行情并评分</small></div>';
    return;
  }
  var sigNames = {strong_buy:'强烈买入',buy:'买入',hold:'持有',weak_hold:'观望',sell:'卖出'};
  var html = '';
  stocks.forEach(function(s,i){
    var pct = s.change_pct||0;
    var pctClass = pct>0?'up':pct<0?'down':'';
    var pctStr = (pct>0?'+':'')+(s.change_pct!=null?s.change_pct.toFixed(2):'-')+'%';
    var price = s.latest_price?s.latest_price.toFixed(2):'-';
    var score = s.composite_score?s.composite_score.toFixed(1):'-';
    var sc = parseFloat(score);
    var scoreColor = sc>=75?'#ff4444':sc>=65?'#ff6b6b':sc>=45?'#d2991d':sc>=30?'#58a6ff':'#3fb950';
    var sigClass = (s.technical_signal||'').toLowerCase();
    var sigName = sigNames[sigClass]||s.technical_signal||'-';
    var rankColor = s.rank<=3?'#ff6b6b':s.rank<=10?'#d2991d':'var(--text-muted)';
    var peStr = s.pe_ttm!=null?(s.pe_ttm<0?'亏损':s.pe_ttm.toFixed(1)):'-';
    var mvStr = s.total_mv?(s.total_mv>=1e8?(s.total_mv/1e8).toFixed(1)+'亿':s.total_mv.toFixed(0)):'-';

    html += '<div class="stock-card" onclick="toggleCard(this)" data-code="'+s.code+'">'+
      '<div class="card-top">'+
        '<div class="card-left">'+
          '<div class="rank" style="color:'+rankColor+'">#'+s.rank+'</div>'+
          '<div class="name-line"><span class="code">'+s.code+'</span><span class="cname">'+s.name+'</span></div>'+
        '</div>'+
        '<div class="card-right">'+
          '<div class="price">'+price+'</div>'+
          '<div class="change '+pctClass+'">'+pctStr+'</div>'+
        '</div>'+
      '</div>'+
      '<div class="card-mid">'+
        '<div class="score-wrap">'+
          '<span class="score-val" style="color:'+scoreColor+'">'+score+'</span>'+
          '<span class="badge '+sigClass+'">'+sigName+'</span>'+
        '</div>'+
      '</div>'+
      '<div class="card-detail">'+
        '<div class="detail-grid">'+
          '<div class="detail-item"><span class="dl">技术面</span><span class="dv">'+(s.technical_score?s.technical_score.toFixed(1):'-')+'</span></div>'+
          '<div class="detail-item"><span class="dl">情绪</span><span class="dv">'+(s.sentiment_score?s.sentiment_score.toFixed(1):'-')+'</span></div>'+
          '<div class="detail-item"><span class="dl">资金流</span><span class="dv">'+(s.fund_flow_score?s.fund_flow_score.toFixed(1):'-')+'</span></div>'+
          '<div class="detail-item"><span class="dl">动量</span><span class="dv">'+(s.momentum_score?s.momentum_score.toFixed(1):'-')+'</span></div>'+
          '<div class="detail-item"><span class="dl">量比</span><span class="dv">'+(s.volume_ratio?s.volume_ratio.toFixed(2):'-')+'</span></div>'+
          '<div class="detail-item"><span class="dl">换手率</span><span class="dv">'+(s.turnover_rate?s.turnover_rate.toFixed(2):'-')+'%</span></div>'+
          '<div class="detail-item"><span class="dl">PE(TTM)</span><span class="dv">'+peStr+'</span></div>'+
          '<div class="detail-item"><span class="dl">市值</span><span class="dv">'+mvStr+'</span></div>'+
        '</div>'+
      '</div>'+
    '</div>';
  });
  el.innerHTML = html;
}

// === Card Expand/Collapse ===
function toggleCard(card) {
  var wasExpanded = card.classList.contains('expanded');
  // Collapse all
  document.querySelectorAll('.stock-card.expanded').forEach(function(c){c.classList.remove('expanded')});
  if(!wasExpanded) card.classList.add('expanded');
}

// === Desktop Table ===
function renderDesktopTable(stocks) {
  var el = document.getElementById('desktopTable');
  if(!stocks.length){el.innerHTML='';return}
  var sigNames = {strong_buy:'强烈买入',buy:'买入',hold:'持有',weak_hold:'观望',sell:'卖出'};
  var headers = ['排名','代码','名称','最新价','涨跌幅%','综合评分','信号','技术','情绪','资金','动量','量比','换手%','PE','总市值'];
  var html = '<table><thead><tr>';
  headers.forEach(function(h){html+='<th>'+h+'</th>'});
  html+='</tr></thead><tbody>';
  stocks.forEach(function(s){
    var pct=s.change_pct||0;
    var pctClass=pct>0?'up':pct<0?'down':'';
    var sc=parseFloat(s.composite_score||0);
    var scoreColor=sc>=75?'#ff4444':sc>=65?'#ff6b6b':sc>=45?'#d2991d':sc>=30?'#58a6ff':'#3fb950';
    var sigClass=(s.technical_signal||'').toLowerCase();
    var sigName=sigNames[sigClass]||s.technical_signal||'-';
    var rankColor=s.rank<=3?'#ff6b6b':s.rank<=10?'#d2991d':'#8b949e';
    html+='<tr>';
    html+='<td style="color:'+rankColor+';font-weight:bold">#'+s.rank+'</td>';
    html+='<td>'+s.code+'</td>';
    html+='<td><a href="/api/stocks/'+s.code+'" target="_blank">'+s.name+'</a></td>';
    html+='<td>'+(s.latest_price?s.latest_price.toFixed(2):'-')+'</td>';
    html+='<td class="'+pctClass+'">'+(pct>0?'+':'')+(s.change_pct!=null?s.change_pct.toFixed(2):'-')+'%</td>';
    html+='<td class="score" style="color:'+scoreColor+'">'+(s.composite_score?s.composite_score.toFixed(1):'-')+'</td>';
    html+='<td><span class="badge '+sigClass+'">'+sigName+'</span></td>';
    html+='<td>'+(s.technical_score?s.technical_score.toFixed(1):'-')+'</td>';
    html+='<td>'+(s.sentiment_score?s.sentiment_score.toFixed(1):'-')+'</td>';
    html+='<td>'+(s.fund_flow_score?s.fund_flow_score.toFixed(1):'-')+'</td>';
    html+='<td>'+(s.momentum_score?s.momentum_score.toFixed(1):'-')+'</td>';
    html+='<td>'+(s.volume_ratio?s.volume_ratio.toFixed(2):'-')+'</td>';
    html+='<td>'+(s.turnover_rate?s.turnover_rate.toFixed(2):'-')+'</td>';
    html+='<td>'+(s.pe_ttm!=null?(s.pe_ttm<0?'亏损':s.pe_ttm.toFixed(1)):'-')+'</td>';
    html+='<td>'+(s.total_mv?(s.total_mv>=1e8?(s.total_mv/1e8).toFixed(2)+'亿':s.total_mv.toFixed(0)):'-')+'</td>';
    html+='</tr>';
  });
  html+='</tbody></table>';
  el.innerHTML = html;
}

// === Search ===
var searchTimer;
document.getElementById('searchInput').addEventListener('input',function(){
  clearTimeout(searchTimer);
  var self = this;
  searchTimer = setTimeout(function(){
    var q = self.value.toLowerCase().trim();
    if(!q){renderSearch(allStocks);return}
    var filtered = allStocks.filter(function(s){
      return s.code.toLowerCase().includes(q)||(s.name||'').toLowerCase().includes(q);
    });
    renderSearch(filtered);
  },200);
});

function renderSearch(stocks) {
  var el = document.getElementById('searchResults');
  if(!stocks.length){el.innerHTML='<div class="loading">未找到匹配股票</div>';return}
  var sigNames = {strong_buy:'强烈买入',buy:'买入',hold:'持有',weak_hold:'观望',sell:'卖出'};
  var html = '';
  stocks.slice(0,30).forEach(function(s){
    var pct = s.change_pct||0;
    var pctClass = pct>0?'up':pct<0?'down':'';
    var pctStr = (pct>0?'+':'')+(s.change_pct!=null?s.change_pct.toFixed(2):'-')+'%';
    var sc = parseFloat(s.composite_score||0);
    var scoreColor = sc>=75?'#ff4444':sc>=65?'#ff6b6b':sc>=45?'#d2991d':sc>=30?'#58a6ff':'#3fb950';
    var sigClass = (s.technical_signal||'').toLowerCase();
    var sigName = sigNames[sigClass]||s.technical_signal||'-';
    html += '<div class="stock-card" style="cursor:default">'+
      '<div class="card-top">'+
        '<div class="card-left">'+
          '<div class="name-line"><span class="code">'+s.code+'</span><span class="cname">'+s.name+'</span></div>'+
        '</div>'+
        '<div class="card-right">'+
          '<div class="price">'+(s.latest_price?s.latest_price.toFixed(2):'-')+'</div>'+
          '<div class="change '+pctClass+'">'+pctStr+'</div>'+
        '</div>'+
      '</div>'+
      '<div class="card-mid">'+
        '<div class="score-wrap">'+
          '<span class="score-val" style="font-size:18px;color:'+scoreColor+'">'+(s.composite_score?s.composite_score.toFixed(1):'-')+'</span>'+
          '<span class="badge '+sigClass+'">'+sigName+'</span>'+
        '</div>'+
      '</div>'+
    '</div>';
  });
  if(stocks.length>30) html+='<div class="pull-hint">仅显示前30条，请输入更精确的关键词</div>';
  el.innerHTML = html;
}

// === About Update ===
function updateAbout() {
  document.getElementById('aboutCount').textContent = allStocks.length||'--';
  document.getElementById('aboutWS').innerHTML = ws&&ws.readyState===WebSocket.OPEN?
    '<span style="color:#3fb950">已连接</span>':'<span style="color:#f85149">未连接</span>';
}

// === WebSocket ===
function connectWS() {
  var protocol = location.protocol==='https:'?'wss:':'ws:';
  ws = new WebSocket(protocol+'//'+location.host+'/ws/live');
  ws.onopen = function(){
    document.getElementById('marketBadge').innerHTML = '<span class="dot green"></span> 实时连接';
  };
  ws.onmessage = function(e){
    var msg = JSON.parse(e.data);
    if(msg.type==='ranking_snapshot'&&msg.data){
      allStocks = msg.data;
      if(currentTab==='tabRanking') renderAll(msg.data);
      else if(currentTab==='tabSearch'){
        var q = document.getElementById('searchInput').value.toLowerCase().trim();
        renderSearch(q?allStocks.filter(function(s){return s.code.toLowerCase().includes(q)||(s.name||'').toLowerCase().includes(q)}):allStocks);
      }
      var now = new Date(msg.timestamp);
      document.getElementById('updateTime').textContent = '更新 '+now.toLocaleTimeString();
      document.getElementById('updateTime').style.display = 'inline';
      renderStats(allStocks);
      updateAbout();
    } else if(msg.type==='market_status'){
      var names = {open:'交易中',lunch_break:'午间休市',closed:'已收盘'};
      var statusName = names[msg.status]||msg.status;
      var dotColor = msg.status==='open'?'green':msg.status==='lunch_break'?'yellow':'red';
      document.getElementById('marketBadge').innerHTML = '<span class="dot '+dotColor+'"></span> '+statusName;
    } else if(msg.type==='alert'){
      showToast('🚨 '+msg.message+' - '+msg.code);
    }
  };
  ws.onclose = function(){
    document.getElementById('marketBadge').innerHTML = '<span class="dot red"></span> 连接断开';
    document.getElementById('updateTime').style.display = 'none';
    updateAbout();
    setTimeout(connectWS,3000);
  };
  ws.onerror = function(){
    updateAbout();
  };
}

// === Pull-to-refresh (touch) ===
var touchStartY = 0;
var pullEl = null;
document.addEventListener('touchstart',function(e){touchStartY=e.touches[0].clientY}, {passive:true});
document.addEventListener('touchmove',function(e){
  if(window.scrollY===0&&e.touches[0].clientY-touchStartY>80){
    if(!pullEl){
      pullEl = document.createElement('div');
      pullEl.className='pull-hint';
      pullEl.textContent='↓ 松开刷新';
      document.getElementById('stockList').prepend(pullEl);
    }
  }
},{passive:true});
document.addEventListener('touchend',function(){
  if(pullEl&&window.scrollY===0){
    pullEl.textContent='⟳ 刷新中...';
    fetchRankings();
    setTimeout(function(){if(pullEl)pullEl.remove();pullEl=null},1000);
  }else if(pullEl){pullEl.remove();pullEl=null}
});

// === Init ===
fetchRankings();
connectWS();
// fallback polling
setInterval(function(){if(!ws||ws.readyState!==WebSocket.OPEN)fetchRankings()},30000);

// === Service Worker Registration ===
if('serviceWorker' in navigator){
  navigator.serviceWorker.register('/sw.js').then(function(reg){
    console.log('SW registered:', reg.scope);
  }).catch(function(err){
    console.log('SW registration failed:', err);
  });
}
</script>
</body>
</html>"""


SW_JS = """const CACHE_NAME = 'stock-tracker-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/manifest.json',
  '/favicon.svg',
  '/api/health',
];

// Install: pre-cache core assets
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      console.log('SW: Caching core assets');
      return cache.addAll(ASSETS_TO_CACHE).catch(function(err) {
        console.log('SW: Cache addAll error (some may be API calls):', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(keys.filter(function(k) { return k !== CACHE_NAME; }).map(function(k) { return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

// Fetch: network-first for API, cache-first for static
self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);

  // Skip non-GET
  if (event.request.method !== 'GET') return;

  // API calls: network-first, fall back to cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(function(response) {
          var cloned = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, cloned);
          });
          return response;
        })
        .catch(function() {
          return caches.match(event.request).then(function(cached) {
            return cached || new Response(JSON.stringify({error:'offline'}), {
              status: 503,
              headers: {'Content-Type': 'application/json'}
            });
          });
        })
    );
    return;
  }

  // Static assets + page: cache-first
  event.respondWith(
    caches.match(event.request).then(function(cached) {
      return cached || fetch(event.request).then(function(response) {
        var cloned = response.clone();
        caches.open(CACHE_NAME).then(function(cache) {
          cache.put(event.request, cloned);
        });
        return response;
      });
    })
  );
});"""

MANIFEST_JSON = {
    "name": "A股实时追踪 - 高价值股智能评分",
    "short_name": "股票追踪",
    "description": "实时追踪A股市场，综合技术分析、新闻情绪、资金流向多维度智能评分",
    "start_url": "/",
    "display": "standalone",
    "orientation": "portrait-primary",
    "theme_color": "#0d1117",
    "background_color": "#0d1117",
    "icons": [
        {
            "src": "/favicon.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable"
        }
    ],
    "categories": ["finance", "utilities"],
    "lang": "zh-CN"
}

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#161b22"/>
    </linearGradient>
  </defs>
  <rect width="100" height="100" rx="20" fill="url(#bg)"/>
  <text x="50" y="40" font-size="22" text-anchor="middle" fill="#8b949e" font-family="Arial,sans-serif" font-weight="bold">A股</text>
  <polygon points="50,48 62,68 50,62 38,68" fill="#ff6b6b"/>
  <line x1="30" y1="80" x2="70" y2="80" stroke="#3fb950" stroke-width="3" stroke-linecap="round"/>
  <line x1="35" y1="74" x2="35" y2="84" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="50" y1="70" x2="50" y2="86" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="65" y1="76" x2="65" y2="82" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round"/>
</svg>"""


# 保活端点（防止免费云服务休眠）
@app.get("/ping")
async def ping():
    """Keepalive endpoint for free tier services"""
    return {"status": "alive", "timestamp": __import__("datetime").datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=SERVER_PORT,
        reload=False,
        log_level=LOG_LEVEL.lower(),
    )
