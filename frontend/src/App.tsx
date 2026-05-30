/**
 * A股高价值股实时追踪系统 - 主应用
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Layout, Typography, Space, Card, Statistic, Row, Col } from 'antd';
import {
  RiseOutlined,
  ThunderboltOutlined,
  FundOutlined,
  StarOutlined,
  DollarOutlined,
} from '@ant-design/icons';

import { useRankingStore, RankingItem } from './store/rankingStore';
import { useWebSocket } from './hooks/useWebSocket';
import RankingTable from './components/RankingTable';
import StockDetail from './components/StockDetail';
import SearchBar from './components/SearchBar';
import MarketStatus from './components/MarketStatus';
import AlertNotification from './components/AlertNotification';

const { Header, Content } = Layout;
const { Text } = Typography;

const App: React.FC = () => {
  const rankings = useRankingStore((s) => s.rankings);
  const setSelectedStock = useRankingStore((s) => s.setSelectedStock);
  const selectedStock = useRankingStore((s) => s.selectedStock);

  const [detailOpen, setDetailOpen] = useState(false);

  // 启动WebSocket连接
  useWebSocket();

  const handleSelectStock = useCallback((stock: RankingItem) => {
    setSelectedStock(stock);
    setDetailOpen(true);
  }, [setSelectedStock]);

  const handleCloseDetail = useCallback(() => {
    setDetailOpen(false);
  }, []);

  // 统计数据
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

  return (
    <Layout className="app-layout">
      <Header className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <RiseOutlined style={{ fontSize: 24, color: '#faad14' }} />
          <h1>A股高价值股实时追踪</h1>
        </div>

        <div className="header-right">
          <SearchBar onSelectStock={handleSelectStock} />
          <MarketStatus />
          <AlertNotification />
        </div>
      </Header>

      <Content className="app-content">
        {/* 统计概览 */}
        <div className="stat-cards">
          <Card className="stat-card" size="small">
            <Statistic
              title="追踪股票"
              value={rankings.length}
              prefix={<FundOutlined />}
              suffix="只"
            />
          </Card>
          <Card className="stat-card" size="small">
            <Statistic
              title="平均评分"
              value={avgScore}
              prefix={<StarOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
          <Card className="stat-card" size="small">
            <Statistic
              title="强烈买入/买入"
              value={topCount}
              prefix={<ThunderboltOutlined />}
              suffix="只"
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
          <Card className="stat-card" size="small">
            <Statistic
              title="今日最强"
              value={topGainer?.name || '-'}
              suffix={
                topGainer ? (
                  <span style={{
                    color: (topGainer.change_pct || 0) >= 0 ? '#cf1322' : '#52c41a',
                    fontSize: 14,
                  }}>
                    {(topGainer.change_pct || 0) >= 0 ? '+' : ''}{topGainer.change_pct?.toFixed(2)}%
                  </span>
                ) : undefined
              }
              prefix={<DollarOutlined />}
            />
          </Card>
          <Card className="stat-card" size="small">
            <Statistic
              title="最高评分股"
              value={bestScore?.name || '-'}
              suffix={
                bestScore ? (
                  <span style={{ color: '#cf1322', fontSize: 14 }}>
                    {bestScore.composite_score.toFixed(1)}分
                  </span>
                ) : undefined
              }
              prefix={<RiseOutlined />}
            />
          </Card>
        </div>

        {/* 排名表 */}
        <Card
          title={
            <Space>
              <span style={{ fontWeight: 'bold', fontSize: 16 }}>Top 50 高价值股排名</span>
              <Text type="secondary" style={{ fontSize: 12 }}>
                （综合技术面35% + 情绪20% + 资金流20% + 动量15% + 成交量10%）
              </Text>
            </Space>
          }
          bodyStyle={{ padding: '8px 0' }}
        >
          <RankingTable onSelectStock={handleSelectStock} />
        </Card>

        {/* 个股详情抽屉 */}
        <StockDetail
          open={detailOpen}
          onClose={handleCloseDetail}
        />
      </Content>
    </Layout>
  );
};

export default App;
