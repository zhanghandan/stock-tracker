/**
 * Top50排名表 - 核心组件
 */
import React, { useMemo } from 'react';
import { Table, Tag, Tooltip } from 'antd';
import { CaretUpOutlined, CaretDownOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useRankingStore, RankingItem } from '../store/rankingStore';
import {
  formatPrice, formatChangePct, formatBigNumber,
  getScoreColor, changeColorClass, formatPE,
} from '../utils/formatters';
import { SIGNAL_COLORS, SIGNAL_ZH } from '../utils/constants';

interface Props {
  onSelectStock: (stock: RankingItem) => void;
}

const RankingTable: React.FC<Props> = ({ onSelectStock }) => {
  const rankings = useRankingStore((s) => s.rankings);

  const columns: ColumnsType<RankingItem> = useMemo(() => [
    {
      title: '排名',
      dataIndex: 'rank',
      key: 'rank',
      width: 60,
      fixed: 'left' as const,
      responsive: ['xs' as const, 'sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (rank: number) => {
        let color = '#999';
        if (rank <= 3) color = '#cf1322';
        else if (rank <= 10) color = '#f5222d';
        return <span style={{ fontWeight: 'bold', color, fontSize: 14 }}>#{rank}</span>;
      },
    },
    {
      title: '代码',
      dataIndex: 'code',
      key: 'code',
      width: 80,
      responsive: ['xs' as const, 'sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
      fixed: 'left' as const,
      responsive: ['xs' as const, 'sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (name: string, record) => (
        <a onClick={() => onSelectStock(record)} style={{ fontWeight: 500 }}>
          {name}
        </a>
      ),
    },
    {
      title: '最新价',
      dataIndex: 'latest_price',
      key: 'latest_price',
      width: 90,
      align: 'right' as const,
      responsive: ['xs' as const, 'sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => formatPrice(v),
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      key: 'change_pct',
      width: 100,
      align: 'right' as const,
      responsive: ['xs' as const, 'sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      sorter: (a, b) => (a.change_pct || 0) - (b.change_pct || 0),
      render: (pct: number) => (
        <span className={changeColorClass(pct)}>
          {pct > 0 ? <CaretUpOutlined /> : pct < 0 ? <CaretDownOutlined /> : null}
          {' '}{formatChangePct(pct)}
        </span>
      ),
    },
    {
      title: '综合评分',
      dataIndex: 'composite_score',
      key: 'composite_score',
      width: 110,
      align: 'center' as const,
      responsive: ['xs' as const, 'sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      sorter: (a, b) => a.composite_score - b.composite_score,
      defaultSortOrder: 'descend' as const,
      render: (score: number) => (
        <Tooltip title={`技术:${score}`}>
          <span style={{
            color: getScoreColor(score),
            fontWeight: 'bold',
            fontSize: 15,
          }}>
            {score.toFixed(1)}
          </span>
        </Tooltip>
      ),
    },
    {
      title: '信号',
      dataIndex: 'technical_signal',
      key: 'technical_signal',
      width: 95,
      align: 'center' as const,
      responsive: ['xs' as const, 'sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (signal: string) => (
        <Tag color={SIGNAL_COLORS[signal] || '#999'} style={{ margin: 0 }}>
          {SIGNAL_ZH[signal] || signal}
        </Tag>
      ),
    },
    {
      title: '技术',
      dataIndex: 'technical_score',
      key: 'technical_score',
      width: 75,
      align: 'center' as const,
      responsive: ['sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => (
        <span style={{ color: getScoreColor(v) }}>{v?.toFixed(1)}</span>
      ),
    },
    {
      title: '情绪',
      dataIndex: 'sentiment_score',
      key: 'sentiment_score',
      width: 75,
      align: 'center' as const,
      responsive: ['sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => (
        <span style={{ color: getScoreColor(v) }}>{v?.toFixed(1)}</span>
      ),
    },
    {
      title: '资金',
      dataIndex: 'fund_flow_score',
      key: 'fund_flow_score',
      width: 75,
      align: 'center' as const,
      responsive: ['md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => (
        <span style={{ color: getScoreColor(v) }}>{v?.toFixed(1)}</span>
      ),
    },
    {
      title: '动量',
      dataIndex: 'momentum_score',
      key: 'momentum_score',
      width: 75,
      align: 'center' as const,
      responsive: ['md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => (
        <span style={{ color: getScoreColor(v) }}>{v?.toFixed(1)}</span>
      ),
    },
    {
      title: '量比',
      dataIndex: 'volume_ratio',
      key: 'volume_ratio',
      width: 75,
      align: 'center' as const,
      responsive: ['lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => v?.toFixed(2) || '-',
    },
    {
      title: '换手率%',
      dataIndex: 'turnover_rate',
      key: 'turnover_rate',
      width: 85,
      align: 'right' as const,
      responsive: ['md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => v?.toFixed(2) || '-',
    },
    {
      title: 'PE(TTM)',
      dataIndex: 'pe_ttm',
      key: 'pe_ttm',
      width: 90,
      align: 'right' as const,
      responsive: ['sm' as const, 'md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => formatPE(v),
    },
    {
      title: '总市值',
      dataIndex: 'total_mv',
      key: 'total_mv',
      width: 100,
      align: 'right' as const,
      responsive: ['md' as const, 'lg' as const, 'xl' as const, 'xxl' as const],
      render: (v: number) => formatBigNumber(v),
    },
    {
      title: '60日涨跌',
      dataIndex: 'change_60d',
      key: 'change_60d',
      width: 100,
      align: 'right' as const,
      responsive: ['lg' as const, 'xl' as const, 'xxl' as const],
      render: (pct: number) => (
        <span className={changeColorClass(pct)}>{formatChangePct(pct)}</span>
      ),
    },
  ], [onSelectStock]);

  return (
    <Table
      columns={columns}
      dataSource={rankings}
      rowKey="code"
      size="small"
      scroll={{ x: 'max-content', y: 'calc(100vh - 320px)' }}
      pagination={{ pageSize: 50, showSizeChanger: false, showTotal: (t) => `共 ${t} 只`, responsive: true }}
      onRow={(record) => ({
        onClick: () => onSelectStock(record),
        style: { cursor: 'pointer' },
      })}
      rowClassName={(record) => {
        if (record.rank <= 3) return 'up-bg';
        return '';
      }}
    />
  );
};

export default RankingTable;
