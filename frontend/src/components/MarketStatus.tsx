/**
 * 市场状态指示器
 */
import React from 'react';
import { Tag, Badge, Space, Tooltip } from 'antd';
import { ClockCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { useMarketStore } from '../store/marketStore';
import { useRankingStore } from '../store/rankingStore';
import { MARKET_STATUS_ZH } from '../utils/constants';
import { formatTime } from '../utils/formatters';

const MarketStatus: React.FC = () => {
  const marketStatus = useMarketStore((s) => s.marketStatus);
  const wsStatus = useMarketStore((s) => s.wsStatus);
  const reconnectAttempt = useMarketStore((s) => s.reconnectAttempt);
  const lastUpdated = useRankingStore((s) => s.lastUpdated);

  const statusColor: Record<string, string> = {
    open: '#52c41a',
    lunch_break: '#faad14',
    closed: '#8c8c8c',
  };

  const wsBadge: Record<string, 'success' | 'error' | 'processing'> = {
    connected: 'success',
    disconnected: 'error',
    reconnecting: 'processing',
  };

  return (
    <Space size="middle">
      <Tooltip title={wsStatus === 'reconnecting' ? `重连中(第${reconnectAttempt}次)` : wsStatus}>
        <Badge status={wsBadge[wsStatus]} text={
          wsStatus === 'connected' ? '已连接' :
          wsStatus === 'reconnecting' ? '重连中' : '已断开'
        } />
      </Tooltip>

      <Tag
        icon={<ClockCircleOutlined />}
        color={statusColor[marketStatus]}
        style={{ margin: 0 }}
      >
        {MARKET_STATUS_ZH[marketStatus] || '未知'}
      </Tag>

      {lastUpdated && (
        <Tooltip title={`最新数据: ${lastUpdated}`}>
          <span style={{ color: '#fff8', fontSize: 12 }}>
            <SyncOutlined spin /> {formatTime(lastUpdated)}
          </span>
        </Tooltip>
      )}
    </Space>
  );
};

export default MarketStatus;
