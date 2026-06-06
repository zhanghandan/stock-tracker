/**
 * A股实时追踪 - Professional Terminal App
 * v2.1 - AI Chat + AI Ranking + K-line search
 */
import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { Typography, Tag, Input } from 'antd';
import {
  RiseOutlined, ThunderboltOutlined, StarOutlined,
  DollarOutlined, AlertOutlined, BarChartOutlined,
  SearchOutlined, OrderedListOutlined, RobotOutlined,
} from '@ant-design/icons';

import { useRankingStore, RankingItem } from './store/rankingStore';
import { useWebSocket } from './hooks/useWebSocket';
import StockDetail from './components/StockDetail';
import MarketStatus from './components/MarketStatus';
import AlertNotification from './components/AlertNotification';
import CandlestickChart from './components/CandlestickChart';
import AIAnalysis from './components/AIAnalysis';

const { Text } = Typography;

interface AIRankingItem {
  code: string;
  name: string;
  ai_rank: number;
  reason: string;
  risk: string;
  advice: string;
}

const App: React.FC = () => {
  const rankings = useRankingStore((s) => s.rankings);
  const setSelectedStock = useRankingStore((s) => s.setSelectedStock);
  const selectedStock = useRankingStore((s) => s.selectedStock);
  const lastUpdated = useRankingStore((s) => s.lastUpdated);

  const [detailOpen, setDetailOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'chart' | 'list' | 'ai'>('chart');
  const [mobileTab, setMobileTab] = useState<'chart' | 'list' | 'ai'>('chart');
  const [selectedCode, setSelectedCode] = useState<string>('');
  const [klineCode, setKlineCode] = useState<string>('');
  const [klineInput, setKlineInput] = useState<string>('');
  const [aiRankings, setAiRankings] = useState<AIRankingItem[]>([]);
  const [aiRankMode, setAiRankMode] = useState(false);
  const [aiRankLoading, setAiRankLoading] = useState(false);

  // Start WebSocket
  useWebSocket();

  // HTTP fallback: fetch rankings immediately
  useEffect(() => {
    if (rankings.length > 0) return;
    fetch('/api/ranking?limit=50')
      .then(r => r.json())
      .then(data => {
        if (data?.items?.length) {
          useRankingStore.getState().setRankings(data.items);
        }
      })
      .catch(() => {});
  }, []);

  // Select first stock by default
  useEffect(() => {
    if (!selectedCode && rankings.length > 0) {
      setSelectedCode(rankings[0].code);
      setKlineCode(rankings[0].code);
    }
  }, [rankings, selectedCode]);

  const handleSelectStock = useCallback((stock: RankingItem) => {
    setSelectedStock(stock);
    setSelectedCode(stock.code);
    setKlineCode(stock.code);
    setDetailOpen(true);
  }, [setSelectedStock]);

  // Fetch AI ranking
  const handleAIRanking = useCallback(async (externalRankings?: AIRankingItem[]) => {
    if (externalRankings) {
      setAiRankings(externalRankings);
      setAiRankMode(true);
      return;
    }

    setAiRankLoading(true);
    try {
      const res = await fetch('/api/ai/rank', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.rankings?.length) {
          setAiRankings(data.rankings);
          setAiRankMode(true);
        }
      }
    } catch {
      // silent
    } finally {
      setAiRankLoading(false);
    }
  }, []);

  // K-line search
  const handleKlineSearch = () => {
    const code = klineInput.trim();
    if (code && /^\d{6}$/.test(code)) {
      setKlineCode(code);
      setSelectedCode(code);
    }
  };

  // Merge ranking data - use AI order if in AI mode
  const displayRankings = useMemo(() => {
    if (!aiRankMode || aiRankings.length === 0) return rankings;

    // Create lookup map from rankings
    const lookup: Record<string, RankingItem> = {};
    rankings.forEach(r => { lookup[r.code] = r; });

    // AI ranked order
    const merged: (RankingItem & { ai_rank?: number; ai_reason?: string; ai_risk?: string; ai_advice?: string })[] = [];
    aiRankings.forEach(ai => {
      const stock = lookup[ai.code];
      if (stock) {
        merged.push({ ...stock, ai_rank: ai.ai_rank, ai_reason: ai.reason, ai_risk: ai.risk, ai_advice: ai.advice });
      }
    });

    // Append unranked stocks at the end
    const rankedCodes = new Set(aiRankings.map(a => a.code));
    rankings.forEach(r => {
      if (!rankedCodes.has(r.code)) {
        merged.push(r);
      }
    });

    return merged;
  }, [rankings, aiRankings, aiRankMode]);

  // Stats
  const topCount = rankings.filter((s) => s.composite_score >= 65).length;
  const avgScore = rankings.length > 0
    ? (rankings.reduce((a, b) => a + b.composite_score, 0) / rankings.length).toFixed(1)
    : '0';
  const topGainer = rankings.length > 0
    ? rankings.reduce((a, b) => (a.change_pct || 0) > (b.change_pct || 0) ? a : b)
    : null;
  const bestScore = rankings.length > 0
    ? rankings.reduce((a, b) => a.composite_score > b.composite_score ? a : b)
    : null;

  // Score color
  const getScoreColor = (score: number) => {
    if (score >= 75) return 'score-hot';
    if (score >= 60) return 'score-warm';
    return 'score-cool';
  };

  // Signal tag
  const getSignalTag = (signal: string) => {
    const map: Record<string, { color: string; text: string }> = {
      STRONG_BUY: { color: '#f44b5e', text: '强买' },
      BUY: { color: '#ff6b6b', text: '买入' },
      HOLD: { color: '#f0a53d', text: '持有' },
      WEAK_HOLD: { color: '#4a5ee5', text: '观望' },
      SELL: { color: '#3ec786', text: '卖出' },
    };
    const s = map[signal] || { color: '#5a6470', text: signal };
    return <Tag color={s.color} style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{s.text}</Tag>;
  };

  // AI advice tag
  const getAdviceTag = (advice: string) => {
    const map: Record<string, { color: string; text: string }> = {
      buy: { color: '#f44b5e', text: '🟢买入' },
      hold: { color: '#f0a53d', text: '🟡持有' },
      wait: { color: '#4a5ee5', text: '🔵观望' },
    };
    const s = map[advice] || { color: '#5a6470', text: advice };
    return <Tag color={s.color} style={{ fontSize: 10 }}>{s.text}</Tag>;
  };

  return (
    <div className="terminal-layout">
      {/* ===== TOP BAR ===== */}
      <div className="top-bar">
        <div className="top-bar-left">
          <span className="top-bar-logo">│ STOCK-TRACKER │</span>
          <MarketStatus />
          <span className="top-bar-status">
            {lastUpdated ? `LAST: ${new Date(lastUpdated).toLocaleTimeString()}` : 'LOADING...'}
          </span>
        </div>
        <div className="top-bar-right">
          <AlertNotification />
        </div>
      </div>

      {/* ===== LEFT PANEL - Stock List ===== */}
      <div className="panel-left">
        <div className="panel-header">
          <span>📊 TOP 50 RANKINGS</span>
          <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {rankings.length} stks
          </span>
        </div>

        {/* Stat bar */}
        <div className="stat-bar">
          <div className="stat-chip">
            <div className="chip-val">{avgScore}</div>
            <div style={{ color: 'var(--text-muted)' }}>AVG</div>
          </div>
          <div className="stat-chip">
            <div className="chip-val" style={{ color: 'var(--up-color)' }}>{topCount}</div>
            <div style={{ color: 'var(--text-muted)' }}>BUY</div>
          </div>
          <div className="stat-chip">
            <div className="chip-val" style={{ color: 'var(--warning)' }}>
              {topGainer?.change_pct ? `${topGainer.change_pct >= 0 ? '+' : ''}${topGainer.change_pct.toFixed(1)}%` : '-'}
            </div>
            <div style={{ color: 'var(--text-muted)' }}>TOPΔ</div>
          </div>
          <div className="stat-chip">
            <div className="chip-val">{bestScore?.code || '-'}</div>
            <div style={{ color: 'var(--text-muted)' }}>BEST</div>
          </div>
        </div>

        {/* Stock list */}
        <div className="panel-list">
          {displayRankings.map((s, i) => (
            <div
              key={s.code}
              className={`panel-list-item ${selectedCode === s.code ? 'selected' : ''}`}
              onClick={() => handleSelectStock(s)}
            >
              <span style={{ color: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)', minWidth: 20 }}>
                {aiRankMode && s.ai_rank ? (
                  <span className="ai-rank-badge" style={{ width: 18, height: 18, fontSize: 9 }}>{s.ai_rank}</span>
                ) : i + 1}
              </span>
              <span className="stock-code">{s.code}</span>
              <span className="stock-name">{s.name}</span>
              <span className={`stock-score ${getScoreColor(s.composite_score)}`}>
                {s.composite_score.toFixed(0)}
              </span>
              <span className="stock-change" style={{ color: (s.change_pct || 0) >= 0 ? 'var(--up-color)' : 'var(--down-color)' }}>
                {(s.change_pct || 0) >= 0 ? '+' : ''}{s.change_pct?.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ===== CENTER PANEL - Chart / Table ===== */}
      <div className="panel-center">
        <div className="panel-tabs">
          <div
            className={`panel-tab ${activeTab === 'chart' ? 'active' : ''}`}
            onClick={() => setActiveTab('chart')}
          >
            <BarChartOutlined /> K-LINE
          </div>
          <div
            className={`panel-tab ${activeTab === 'list' ? 'active' : ''}`}
            onClick={() => setActiveTab('list')}
          >
            <OrderedListOutlined /> TABLE
          </div>
          <div
            className={`panel-tab ${activeTab === 'ai' ? 'active' : ''}`}
            onClick={() => setActiveTab('ai')}
          >
            <RobotOutlined /> AI INSIGHT
          </div>

          {/* AI Rank Toggle */}
          {activeTab === 'list' && (
            <div style={{ marginLeft: 'auto', padding: '4px 12px', display: 'flex', alignItems: 'center' }}>
              <div
                className={`ai-rank-toggle ${aiRankMode ? 'active' : ''}`}
                onClick={() => aiRankMode ? setAiRankMode(false) : handleAIRanking()}
                title="AI重新排名Top30"
              >
                <RobotOutlined style={{ fontSize: 13 }} />
                {aiRankLoading ? '排名中...' : aiRankMode ? 'AI排名 ON' : 'AI排名'}
              </div>
            </div>
          )}
        </div>

        {/* Ticker tape */}
        {activeTab !== 'ai' && (
          <div className="ticker-tape">
            {rankings.slice(0, 10).map((s) => (
              <div
                key={s.code}
                className="ticker-item"
                onClick={() => handleSelectStock(s)}
                style={{
                  color: (s.change_pct || 0) >= 0 ? 'var(--up-color)' : 'var(--down-color)',
                  border: `1px solid ${(s.change_pct || 0) >= 0 ? 'rgba(244,75,94,0.2)' : 'rgba(62,199,134,0.2)'}`
                }}
              >
                <span>{s.code}</span>
                <span style={{ fontWeight: 600 }}>{(s.change_pct || 0) >= 0 ? '+' : ''}{s.change_pct?.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        )}

        {/* Chart with stock code search */}
        {activeTab === 'chart' && (
          <div className="chart-container" style={{ display: 'flex', flexDirection: 'column' }}>
            {/* K-line search bar */}
            <div className="kline-search">
              <SearchOutlined style={{ color: 'var(--text-muted)', fontSize: 12 }} />
              <input
                className="kline-search-input"
                placeholder="输入代码如 600519"
                value={klineInput}
                onChange={e => setKlineInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleKlineSearch(); }}
                maxLength={6}
              />
              <button className="kline-search-btn" onClick={handleKlineSearch}>
                查看K线
              </button>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                当前: <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{klineCode || '-'}</span>
              </span>
            </div>
            <div style={{ flex: 1 }}>
              <CandlestickChart code={klineCode || rankings[0]?.code || ''} live={true} />
            </div>
          </div>
        )}

        {/* Table view with AI ranking */}
        {activeTab === 'list' && (
          <div style={{ flex: 1, overflow: 'auto', padding: '0 12px' }}>
            {displayRankings.length > 0 ? (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr>
                    {['#', '代码', '名称', '最新价', '涨跌%', '综合评分', '信号', '技术', '情绪', '资金', '动量',
                      ...(aiRankMode ? ['AI推荐理由', 'AI建议'] : [])].map(h => (
                      <th key={h} style={{ padding: '8px 6px', textAlign: 'left', borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayRankings.map((s: any, i) => (
                    <tr
                      key={s.code}
                      onClick={() => handleSelectStock(s)}
                      style={{
                        cursor: 'pointer',
                        background: selectedCode === s.code ? 'var(--bg-hover)' : 'transparent',
                      }}
                      onMouseEnter={(e) => { if (selectedCode !== s.code) e.currentTarget.style.background = 'var(--bg-card)'; }}
                      onMouseLeave={(e) => { if (selectedCode !== s.code) e.currentTarget.style.background = 'transparent'; }}
                    >
                      <td style={{ padding: '6px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {aiRankMode && s.ai_rank ? (
                          <span className="ai-rank-badge" style={{ width: 22, height: 22, fontSize: 10 }}>{s.ai_rank}</span>
                        ) : i + 1}
                      </td>
                      <td style={{ padding: '6px', color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{s.code}</td>
                      <td style={{ padding: '6px' }}>{s.name}</td>
                      <td style={{ padding: '6px', fontFamily: 'var(--font-mono)' }}>{s.latest_price?.toFixed(2) || '-'}</td>
                      <td style={{
                        padding: '6px',
                        fontFamily: 'var(--font-mono)',
                        color: (s.change_pct || 0) >= 0 ? 'var(--up-color)' : 'var(--down-color)',
                        fontWeight: 600,
                      }}>
                        {(s.change_pct || 0) >= 0 ? '+' : ''}{s.change_pct?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '6px', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                        <span style={{ color: s.composite_score >= 75 ? '#f44b5e' : s.composite_score >= 60 ? '#f0a53d' : '#3ec786' }}>
                          {s.composite_score.toFixed(1)}
                        </span>
                      </td>
                      <td style={{ padding: '6px' }}>{getSignalTag(s.technical_signal || '')}</td>
                      <td style={{ padding: '6px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{s.technical_score?.toFixed(1)}</td>
                      <td style={{ padding: '6px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{s.sentiment_score?.toFixed(1)}</td>
                      <td style={{ padding: '6px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{s.fund_flow_score?.toFixed(1)}</td>
                      <td style={{ padding: '6px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{s.momentum_score?.toFixed(1)}</td>
                      {aiRankMode && (
                        <>
                          <td style={{ padding: '6px' }}>
                            <span className="ai-reason" title={`${s.ai_reason || ''}${s.ai_risk ? ' | ⚠风险: ' + s.ai_risk : ''}`}>{s.ai_reason || '-'}</span>
                          </td>
                          <td style={{ padding: '6px' }}>{s.ai_advice ? getAdviceTag(s.ai_advice) : '-'}</td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                <ThunderboltOutlined style={{ fontSize: 32 }} />
                <div style={{ marginTop: 12 }}>等待实时数据...</div>
              </div>
            )}
          </div>
        )}

        {/* AI Insight tab */}
        {activeTab === 'ai' && (
          <AIAnalysis
            code={selectedCode || rankings[0]?.code}
            rankings={rankings}
            onAIRanking={handleAIRanking}
          />
        )}
      </div>

      {/* ===== RIGHT PANEL - AI Chat ===== */}
      <div className="panel-right">
        <AIAnalysis
          code={selectedCode || rankings[0]?.code}
          rankings={rankings}
          compact
          onAIRanking={handleAIRanking}
        />
      </div>

      {/* ===== Stock Detail Drawer ===== */}
      <StockDetail open={detailOpen} onClose={() => setDetailOpen(false)} />

      {/* ===== Mobile Bottom Nav ===== */}
      <div className="bottom-nav" style={{ display: 'none' }}>
        <div className={`bottom-nav-item ${mobileTab === 'chart' ? 'active' : ''}`} onClick={() => { setMobileTab('chart'); setActiveTab('chart'); }}>
          <BarChartOutlined style={{ fontSize: 18 }} />
          <span>K线</span>
        </div>
        <div className={`bottom-nav-item ${mobileTab === 'list' ? 'active' : ''}`} onClick={() => { setMobileTab('list'); setActiveTab('list'); }}>
          <OrderedListOutlined style={{ fontSize: 18 }} />
          <span>排名</span>
        </div>
        <div className={`bottom-nav-item ${mobileTab === 'ai' ? 'active' : ''}`} onClick={() => { setMobileTab('ai'); setActiveTab('ai'); }}>
          <RobotOutlined style={{ fontSize: 18 }} />
          <span>AI</span>
        </div>
      </div>
    </div>
  );
};

export default App;
