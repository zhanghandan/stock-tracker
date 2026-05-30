/**
 * 个股详情面板
 */
import React, { useEffect, useState } from 'react';
import { Drawer, Descriptions, Tag, Spin, Tabs, Table, Statistic, Row, Col, Card } from 'antd';
import { CaretUpOutlined, CaretDownOutlined } from '@ant-design/icons';
import { useRankingStore } from '../store/rankingStore';
import { useStockData } from '../hooks/useStockData';
import CandlestickChart from './CandlestickChart';
import { SIGNAL_COLORS, SIGNAL_ZH } from '../utils/constants';
import {
  formatPrice, formatChangePct, formatBigNumber,
  changeColorClass, formatPE, getScoreColor,
} from '../utils/formatters';

interface Props {
  open: boolean;
  onClose: () => void;
}

const StockDetail: React.FC<Props> = ({ open, onClose }) => {
  const selectedStock = useRankingStore((s) => s.selectedStock);
  const { fetchStockDetail, fetchNews } = useStockData();
  const [detail, setDetail] = useState<any>(null);
  const [news, setNews] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedStock || !open) return;

    setLoading(true);
    Promise.all([
      fetchStockDetail(selectedStock.code),
      fetchNews(selectedStock.code),
    ]).then(([detailData, newsData]) => {
      setDetail(detailData);
      setNews(newsData?.items || []);
    }).finally(() => setLoading(false));
  }, [selectedStock?.code, open]);

  if (!selectedStock) return null;

  const s = selectedStock;

  const newsColumns = [
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: '情绪',
      dataIndex: 'sentiment_label',
      key: 'sentiment_label',
      width: 80,
      align: 'center' as const,
      render: (label: string) => {
        const colors: Record<string, string> = {
          positive: '#cf1322', negative: '#52c41a', neutral: '#999',
        };
        const zh: Record<string, string> = {
          positive: '正面', negative: '负面', neutral: '中性',
        };
        return <Tag color={colors[label] || '#999'}>{zh[label] || label}</Tag>;
      },
    },
    { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
    { title: '时间', dataIndex: 'publish_time', key: 'publish_time', width: 130 },
  ];

  return (
    <Drawer
      title={
        <span>
          <span style={{ fontWeight: 'bold', fontSize: 16 }}>{s.name}</span>
          <span style={{ color: '#999', marginLeft: 8 }}>{s.code}</span>
          {s.technical_signal && (
            <Tag color={SIGNAL_COLORS[s.technical_signal]} style={{ marginLeft: 8 }}>
              {SIGNAL_ZH[s.technical_signal]}
            </Tag>
          )}
        </span>
      }
      placement="right"
      width={window.innerWidth < 768 ? '100%' : '80%'}
      open={open}
      onClose={onClose}
    >
      {loading ? (
        <Spin tip="加载详情..." style={{ display: 'block', textAlign: 'center', padding: 60 }} />
      ) : (
        <>
          {/* 价格概览 */}
          <Row gutter={[16, 12]} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={8} md={4}>
              <Card size="small">
                <Statistic
                  title="最新价"
                  value={formatPrice(s.latest_price)}
                  valueStyle={{
                    color: (s.change_pct || 0) > 0 ? '#cf1322' : (s.change_pct || 0) < 0 ? '#52c41a' : '#333',
                  }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Card size="small">
                <Statistic
                  title="涨跌幅"
                  value={formatChangePct(s.change_pct)}
                  prefix={s.change_pct && s.change_pct > 0 ? <CaretUpOutlined /> : <CaretDownOutlined />}
                  valueStyle={{ color: (s.change_pct || 0) >= 0 ? '#cf1322' : '#52c41a' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Card size="small">
                <Statistic
                  title="综合评分"
                  value={s.composite_score.toFixed(1)}
                  valueStyle={{ color: getScoreColor(s.composite_score), fontWeight: 'bold' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Card size="small">
                <Statistic title="量比" value={s.volume_ratio?.toFixed(2) || '-'} />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Card size="small">
                <Statistic title="换手率" value={s.turnover_rate?.toFixed(2) + '%' || '-'} />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Card size="small">
                <Statistic title="PE(TTM)" value={formatPE(s.pe_ttm)} />
              </Card>
            </Col>
          </Row>

          {/* 评分细节 */}
          <Card size="small" title="评分子项" style={{ marginBottom: 16 }}>
            <Row gutter={[12, 8]}>
              {(['technical', 'sentiment', 'fund_flow', 'momentum', 'volume'] as const).map((key) => {
                const labels = { technical: '技术面', sentiment: '情绪', fund_flow: '资金流', momentum: '动量', volume: '成交量' };
                const score = s[`${key}_score` as keyof typeof s] as number;
                return (
                  <Col xs={12} sm={8} md={4} key={key} style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: '#999' }}>{labels[key]}</div>
                    <div style={{ fontSize: 22, fontWeight: 'bold', color: getScoreColor(score || 0) }}>
                      {score?.toFixed(1) || '-'}
                    </div>
                    <div style={{ fontSize: 11, color: '#bbb' }}>权重 {(key === 'technical' ? 35 : key === 'sentiment' || key === 'fund_flow' ? 20 : key === 'momentum' ? 15 : 10)}%</div>
                  </Col>
                );
              })}
            </Row>
          </Card>

          {/* K线图 */}
          <div style={{ marginBottom: 16 }}>
            <CandlestickChart code={s.code} name={s.name} height={typeof window !== 'undefined' ? Math.min(380, window.innerHeight * 0.45) : 300} />
          </div>

          {/* 基本面信息 */}
          <Descriptions
            bordered
            size="small"
            column={{ xs: 1, sm: 2, md: 4 }}
            style={{ marginBottom: 16 }}
            title="基本面信息"
          >
            <Descriptions.Item label="总市值">{formatBigNumber(s.total_mv)}</Descriptions.Item>
            <Descriptions.Item label="PE(TTM)">{formatPE(s.pe_ttm)}</Descriptions.Item>
            <Descriptions.Item label="PB">{s.pb?.toFixed(2) || '-'}</Descriptions.Item>
            <Descriptions.Item label="60日涨跌">
              <span className={changeColorClass(s.change_60d)}>{formatChangePct(s.change_60d)}</span>
            </Descriptions.Item>
          </Descriptions>

          {/* 子评分表格 */}
          <Tabs
            defaultActiveKey="news"
            items={[
              {
                key: 'news',
                label: `相关新闻 (${news.length})`,
                children: (
                  <Table
                    columns={newsColumns}
                    dataSource={news}
                    rowKey="id"
                    size="small"
                    pagination={{ pageSize: 10 }}
                  />
                ),
              },
            ]}
          />
        </>
      )}
    </Drawer>
  );
};

export default StockDetail;
