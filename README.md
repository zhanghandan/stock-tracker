# A股高价值股实时追踪系统

实时追踪A股市场，综合**技术分析**、**新闻情绪**、**资金流向**、**动量趋势**和**成交量**五个维度，智能评分排名，筛选出最具投资价值的前50只股票。

---

## 功能特性

### 实时数据
- **全A股行情**: 每5秒刷新约5000只股票实时行情（交易时段）
- **历史K线**: 自动获取并缓存60天日K线数据
- **资金流向**: 实时追踪主力资金（超大单/大单/中单/小单）净流入流出
- **新闻爬取**: 自动爬取个股相关新闻

### 智能分析
- **技术指标**: MA均线、MACD、RSI(6/12/24)、KDJ(9/3/3)、Bollinger Bands
- **情绪分析**: SnowNLP中文NLP分析新闻情绪（正面/负面/中性）
- **多维度评分**: 技术面35% + 情绪20% + 资金流20% + 动量15% + 成交量10%

### 实时仪表盘
- **Top50排名表**: 实时更新，支持多列排序
- **K线图表**: ECharts专业K线图 + MA均线 + 成交量柱
- **个股详情**: 评分细节、基本面信息、新闻情绪
- **WebSocket推送**: 实时数据推送，秒级刷新
- **智能告警**: 高分股票自动提示

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 数据源 | akshare (东方财富/新浪/雪球) |
| 后端 | Python + FastAPI + uvicorn |
| 调度 | APScheduler |
| 数据库 | SQLite (SQLAlchemy + aiosqlite) |
| 技术指标 | pandas-ta |
| NLP | SnowNLP |
| 前端 | React 18 + TypeScript + Vite |
| 图表 | Apache ECharts 5 |
| UI | Ant Design 5 |
| 状态管理 | Zustand |
| 实时通信 | WebSocket |

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+ (前端开发)
- Windows / macOS / Linux

### 1. 安装Python依赖

```bash
cd stock-tracker
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
python scripts/init_db.py
```

### 3. 导入股票列表

```bash
python scripts/seed_stocks.py
```

### 4. （可选）回填历史K线

```bash
python scripts/backfill_history.py
```
> ⚠️ 获取5000只股票的60天历史数据需要30-60分钟，建议在首次使用时执行。

### 5. 启动后端

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后：
- REST API: http://localhost:8000/api/docs
- WebSocket: ws://localhost:8000/ws/live
- 健康检查: http://localhost:8000/api/health

### 6. 启动前端（可选）

```bash
cd frontend
npm install
npm run dev
```

前端仪表盘: http://localhost:5173

### 一键启动（开发模式）

```bash
python scripts/run_dev.py
```

---

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 系统健康检查 |
| `/api/ranking` | GET | Top50排名（支持sort_by参数） |
| `/api/stocks/{code}` | GET | 个股详情 |
| `/api/stocks/{code}/history` | GET | 历史K线数据 |
| `/api/stocks/{code}/news` | GET | 个股新闻+情绪 |
| `/api/stocks/{code}/indicators` | GET | 技术指标 |
| `/api/fund-flow` | GET | 资金流向排名 |
| `/api/search?q=` | GET | 搜索股票 |
| `/ws/live` | WS | 实时数据推送 |

---

## 评分算法

### 综合评分公式

```
composite = technical × 0.35 + sentiment × 0.20 + fund_flow × 0.20
          + momentum × 0.15 + volume × 0.10
```

### 买卖信号

| 分值 | 信号 |
|------|------|
| ≥ 75 + 涨 + 放量 | 🟢 STRONG_BUY 强烈买入 |
| ≥ 65 | 🔵 BUY 买入 |
| 45 ~ 65 | 🟡 HOLD 持有 |
| 30 ~ 45 | 🔷 WEAK_HOLD 观望 |
| < 30 | ⚪ SELL 卖出 |

### 过滤规则

- 自动排除ST/*ST股票
- 排除2元以下低价股
- PE<0或PE>500的股票扣10分修正

---

## 目录结构

```
stock-tracker/
├── backend/
│   ├── main.py              # FastAPI入口
│   ├── config.py            # 配置
│   ├── database.py          # 数据库引擎
│   ├── models.py            # ORM模型(7张表)
│   ├── scheduler.py         # 任务调度
│   ├── collectors/          # 数据采集
│   │   ├── realtime.py      # 实时行情
│   │   ├── historical.py    # 历史K线
│   │   ├── fund_flow.py     # 资金流向
│   │   └── news.py          # 新闻爬取
│   ├── analyzers/           # 分析引擎
│   │   ├── technical.py     # 技术指标
│   │   ├── sentiment.py     # 情绪分析
│   │   └── volume_flow.py   # 成交量分析
│   ├── scoring/             # 评分引擎
│   │   ├── engine.py        # 综合评分
│   │   ├── weights.py       # 权重配置
│   │   └── signals.py       # 信号生成
│   ├── api/                 # API层
│   │   ├── router.py        # REST路由
│   │   ├── websocket.py     # WebSocket
│   │   └── schemas.py       # 数据模型
│   └── utils/               # 工具
├── frontend/                # React前端
├── scripts/                 # 脚本
├── data/                    # SQLite数据
└── logs/                    # 日志
```

---

## 配置

编辑 `backend/config.py` 可自定义：

- **评分权重**: SCORING_WEIGHTS
- **刷新间隔**: REALTIME_INTERVAL_SEC (默认5秒)
- **候选股数量**: CANDIDATE_COUNT (默认200)
- **历史天数**: HISTORY_DAYS (默认60天)
- **排除条件**: EXCLUDE_PRICE_BELOW (默认2元)

权重配置支持4种预设：`default`（均衡）、`aggressive`（激进）、`conservative`（保守）、`short_term`（短线）。

---

## 常见问题

### Q: 非交易时段能看到数据吗？
可以，系统在非交易时段每5分钟静默刷新一次，显示最新的收盘数据。

### Q: 数据来源是什么？
通过 `akshare` 库对接东方财富(EM)、新浪财经(Sina)、雪球(Xueqiu)等平台的公开接口，完全免费，无需API Key。

### Q: 需要多少内存？
约150-200MB（历史数据缓存~50MB + Python进程~100MB + 前端Node进程~50MB）。

### Q: 评分准确吗？
评分模型是基于经典技术分析和多因子模型的综合判断。任何评分系统都不构成投资建议，请结合自己的判断做出投资决策。

---

## ⚠️ 免责声明

本系统仅供学习和研究使用，**不构成任何投资建议**。A股投资有风险，入市需谨慎。系统产生的任何评分、信号和排名仅代表算法计算结果，不代表对未来走势的预测。使用本系统产生的任何投资决策和盈亏后果由用户自行承担。

---

## License

MIT License
