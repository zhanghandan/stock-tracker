"""
ORM模型 - 全部7张表
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Stock(Base):
    """股票元数据"""
    __tablename__ = "stocks"

    code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="股票代码")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="股票名称")
    market: Mapped[str] = mapped_column(String(10), nullable=True, comment="市场 SH/SZ/BJ")
    industry: Mapped[str] = mapped_column(String(100), nullable=True, comment="所属行业")
    list_date: Mapped[str] = mapped_column(String(10), nullable=True, comment="上市日期")
    is_active: Mapped[int] = mapped_column(Integer, default=1, comment="是否活跃")


class StockRealtime(Base):
    """实时行情快照"""
    __tablename__ = "stock_realtime"

    code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="股票代码")
    name: Mapped[str] = mapped_column(String(50), nullable=True, comment="股票名称")
    latest_price: Mapped[float] = mapped_column(Float, nullable=True, comment="最新价")
    change_pct: Mapped[float] = mapped_column(Float, nullable=True, comment="涨跌幅(%)")
    change_amount: Mapped[float] = mapped_column(Float, nullable=True, comment="涨跌额")
    volume_hands: Mapped[float] = mapped_column(Float, nullable=True, comment="成交量(手)")
    turnover_yuan: Mapped[float] = mapped_column(Float, nullable=True, comment="成交额(元)")
    amplitude: Mapped[float] = mapped_column(Float, nullable=True, comment="振幅(%)")
    high: Mapped[float] = mapped_column(Float, nullable=True, comment="最高价")
    low: Mapped[float] = mapped_column(Float, nullable=True, comment="最低价")
    open: Mapped[float] = mapped_column(Float, nullable=True, comment="开盘价")
    prev_close: Mapped[float] = mapped_column(Float, nullable=True, comment="前收盘价")
    volume_ratio: Mapped[float] = mapped_column(Float, nullable=True, comment="量比")
    turnover_rate: Mapped[float] = mapped_column(Float, nullable=True, comment="换手率(%)")
    pe_ttm: Mapped[float] = mapped_column(Float, nullable=True, comment="市盈率(动态)")
    pb: Mapped[float] = mapped_column(Float, nullable=True, comment="市净率")
    total_mv: Mapped[float] = mapped_column(Float, nullable=True, comment="总市值")
    float_mv: Mapped[float] = mapped_column(Float, nullable=True, comment="流通市值")
    change_60d: Mapped[float] = mapped_column(Float, nullable=True, comment="60日涨跌幅")
    change_ytd: Mapped[float] = mapped_column(Float, nullable=True, comment="年初至今涨跌幅")
    updated_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        comment="更新时间"
    )


class StockDaily(Base):
    """历史日K线"""
    __tablename__ = "stock_daily"
    __table_args__ = (
        PrimaryKeyConstraint("code", "trade_date"),
    )

    code: Mapped[str] = mapped_column(String(10), comment="股票代码")
    trade_date: Mapped[str] = mapped_column(String(10), comment="交易日期 YYYY-MM-DD")
    open: Mapped[float] = mapped_column(Float, nullable=True, comment="开盘价")
    high: Mapped[float] = mapped_column(Float, nullable=True, comment="最高价")
    low: Mapped[float] = mapped_column(Float, nullable=True, comment="最低价")
    close: Mapped[float] = mapped_column(Float, nullable=True, comment="收盘价")
    volume: Mapped[float] = mapped_column(Float, nullable=True, comment="成交量(手)")
    amount: Mapped[float] = mapped_column(Float, nullable=True, comment="成交额(元)")
    amplitude: Mapped[float] = mapped_column(Float, nullable=True, comment="振幅(%)")
    change_pct: Mapped[float] = mapped_column(Float, nullable=True, comment="涨跌幅(%)")
    change_amt: Mapped[float] = mapped_column(Float, nullable=True, comment="涨跌额")
    turnover_rate: Mapped[float] = mapped_column(Float, nullable=True, comment="换手率(%)")


class TechnicalIndicator(Base):
    """技术指标"""
    __tablename__ = "technical_indicators"

    code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="股票代码")
    ma5: Mapped[float] = mapped_column(Float, nullable=True)
    ma10: Mapped[float] = mapped_column(Float, nullable=True)
    ma20: Mapped[float] = mapped_column(Float, nullable=True)
    ma60: Mapped[float] = mapped_column(Float, nullable=True)
    macd_dif: Mapped[float] = mapped_column(Float, nullable=True)
    macd_dea: Mapped[float] = mapped_column(Float, nullable=True)
    macd_bar: Mapped[float] = mapped_column(Float, nullable=True, comment="2*(DIF-DEA)")
    rsi_6: Mapped[float] = mapped_column(Float, nullable=True)
    rsi_12: Mapped[float] = mapped_column(Float, nullable=True)
    rsi_24: Mapped[float] = mapped_column(Float, nullable=True)
    kdj_k: Mapped[float] = mapped_column(Float, nullable=True)
    kdj_d: Mapped[float] = mapped_column(Float, nullable=True)
    kdj_j: Mapped[float] = mapped_column(Float, nullable=True)
    boll_upper: Mapped[float] = mapped_column(Float, nullable=True)
    boll_mid: Mapped[float] = mapped_column(Float, nullable=True)
    boll_lower: Mapped[float] = mapped_column(Float, nullable=True)
    vol_ma5: Mapped[float] = mapped_column(Float, nullable=True, comment="5日均量")
    vol_ratio_vs20: Mapped[float] = mapped_column(Float, nullable=True, comment="量/20日均量")
    computed_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


class FundFlow(Base):
    """资金流向"""
    __tablename__ = "fund_flow"
    __table_args__ = (
        PrimaryKeyConstraint("code", "flow_date"),
    )

    code: Mapped[str] = mapped_column(String(10), comment="股票代码")
    flow_date: Mapped[str] = mapped_column(String(10), comment="日期 YYYY-MM-DD")
    main_net_inflow: Mapped[float] = mapped_column(Float, nullable=True, comment="主力净流入(元)")
    main_net_pct: Mapped[float] = mapped_column(Float, nullable=True, comment="主力净流入占比(%)")
    super_large_inflow: Mapped[float] = mapped_column(Float, nullable=True, comment="超大单净流入")
    large_inflow: Mapped[float] = mapped_column(Float, nullable=True, comment="大单净流入")
    medium_inflow: Mapped[float] = mapped_column(Float, nullable=True, comment="中单净流入")
    small_inflow: Mapped[float] = mapped_column(Float, nullable=True, comment="小单净流入")
    updated_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


class NewsArticle(Base):
    """新闻文章"""
    __tablename__ = "news_articles"
    __table_args__ = (
        Index("idx_news_code_time", "code", "publish_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, comment="相关股票代码")
    title: Mapped[str] = mapped_column(Text, nullable=True, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=True, comment="内容")
    source: Mapped[str] = mapped_column(String(100), nullable=True, comment="来源")
    url: Mapped[str] = mapped_column(String(500), nullable=True, comment="链接")
    publish_time: Mapped[str] = mapped_column(String(30), nullable=True, comment="发布时间")
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=True, comment="情绪得分 -1~1")
    sentiment_label: Mapped[str] = mapped_column(String(20), nullable=True, comment="positive/negative/neutral")
    fetched_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


class StockScore(Base):
    """综合评分排名"""
    __tablename__ = "stock_scores"

    code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="股票代码")
    rank: Mapped[int] = mapped_column(Integer, nullable=True, comment="排名")
    composite_score: Mapped[float] = mapped_column(Float, nullable=True, comment="综合评分 0-100")
    technical_score: Mapped[float] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=True)
    fund_flow_score: Mapped[float] = mapped_column(Float, nullable=True)
    momentum_score: Mapped[float] = mapped_column(Float, nullable=True)
    volume_score: Mapped[float] = mapped_column(Float, nullable=True)
    technical_signal: Mapped[str] = mapped_column(String(20), nullable=True, comment="BUY/SELL/HOLD")
    scored_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


class SystemState(Base):
    """系统状态"""
    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
