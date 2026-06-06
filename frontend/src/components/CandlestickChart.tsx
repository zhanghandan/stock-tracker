/**
 * K线图 + MA均线 + 成交量 - ECharts
 * 支持实时更新模式
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin, Empty } from 'antd';

interface Props {
  code: string;
  name?: string;
  height?: number;
  live?: boolean;  // 实时更新模式
}

interface KLineData {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change_pct: number | null;
}

const CandlestickChart: React.FC<Props> = ({ code, name, height = 400, live = false }) => {
  const [data, setData] = useState<KLineData[]>([]);
  const [loading, setLoading] = useState(false);
  const chartRef = useRef<any>(null);

  const fetchData = useCallback(async () => {
    if (!code) {
      setData([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/stocks/${code}/history?days=60`);
      if (!res.ok) {
        console.warn('K线API返回:', res.status);
        setData([]);
        return;
      }
      const json = await res.json();
      if (json?.data && json.data.length > 0) {
        setData(json.data);
      } else {
        setData([]);
      }
    } catch (e) {
      console.error('K线获取失败:', e);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [code]);

  useEffect(() => {
    fetchData();
    // Live mode: refresh every 60s
    if (live) {
      const interval = setInterval(fetchData, 60000);
      return () => clearInterval(interval);
    }
  }, [fetchData, live]);

  // WebSocket实时价格监听
  useEffect(() => {
    if (!live || !data.length) return;
    // Listen for stock_update messages via a custom event
    const handler = (e: CustomEvent) => {
      if (e.detail?.code === code && e.detail?.data?.latest_price) {
        setData(prev => {
          if (!prev.length) return prev;
          const newData = [...prev];
          const last = { ...newData[newData.length - 1] };
          last.close = e.detail.data.latest_price;
          last.high = Math.max(last.high, e.detail.data.latest_price);
          last.low = Math.min(last.low, e.detail.data.latest_price);
          newData[newData.length - 1] = last;
          return newData;
        });
      }
    };
    window.addEventListener('stock_update', handler as any);
    return () => window.removeEventListener('stock_update', handler as any);
  }, [live, code, data.length]);

  if (loading && !data.length) {
    return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height }}><Spin /></div>;
  }
  if (!data.length) {
    return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height }}><Empty description="暂无K线数据" /></div>;
  }

  const dates = data.map((d) => d.trade_date);
  const ohlc = data.map((d) => [d.open, d.close, d.low, d.high]);
  const volumes = data.map((d) => d.volume);
  const closes = data.map((d) => d.close);

  // MA计算
  const calcMA = (period: number) => {
    const result: (number | null)[] = [];
    for (let i = 0; i < closes.length; i++) {
      if (i < period - 1) { result.push(null); continue; }
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += closes[j];
      result.push(+(sum / period).toFixed(2));
    }
    return result;
  };

  const ma5 = calcMA(5);
  const ma10 = calcMA(10);
  const ma20 = calcMA(20);

  // Dark theme colors matching terminal
  const upColor = '#f44b5e';
  const downColor = '#3ec786';
  const bgColor = '#0a0e14';
  const textColor = '#8895a3';
  const borderColor = '#262d36';

  const option = {
    backgroundColor: bgColor,
    animation: live,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#191e25',
      borderColor: borderColor,
      textStyle: { color: '#cdd6e0', fontSize: 12 },
      formatter: (params: any[]) => {
        if (!params || !params.length) return '';
        const date = params[0].axisValue;
        let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`;
        params.forEach((p: any) => {
          if (p.seriesName === '成交量') return;
          const color = p.color || textColor;
          html += `<div style="display:flex;justify-content:space-between;gap:12px">
            <span style="color:${color}">${p.marker} ${p.seriesName}</span>
            <span style="font-family:monospace">${Array.isArray(p.data) ? p.data.join(' / ') : p.data}</span>
          </div>`;
        });
        return html;
      },
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA20', '成交量'],
      top: 0,
      textStyle: { color: textColor, fontSize: 11 },
    },
    grid: [
      { left: '8%', right: '3%', top: '10%', height: '55%' },
      { left: '8%', right: '3%', top: '72%', height: '18%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: borderColor } },
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLabel: {
          rotate: 30,
          fontSize: 10,
          color: textColor,
          formatter: (v: string) => v.slice(5),
        },
        axisLine: { lineStyle: { color: borderColor } },
      },
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        splitArea: { show: true, areaStyle: { color: ['rgba(38,45,54,0.3)', 'transparent'] } },
        axisLabel: { fontSize: 10, color: textColor },
        splitLine: { lineStyle: { color: borderColor } },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: {
          fontSize: 10,
          color: textColor,
          formatter: (v: number) => v >= 1e8 ? (v / 1e8).toFixed(1) + '亿' : (v / 1e4).toFixed(0) + '万',
        },
        splitLine: { lineStyle: { color: borderColor } },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 50, end: 100, bottom: 5, borderColor: borderColor, backgroundColor: 'rgba(18,22,28,0.8)' },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: upColor,
          color0: downColor,
          borderColor: upColor,
          borderColor0: downColor,
        },
      },
      {
        name: 'MA5', type: 'line', data: ma5, xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, lineStyle: { width: 1.5, color: '#ffc53d' }, symbol: 'none',
      },
      {
        name: 'MA10', type: 'line', data: ma10, xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, lineStyle: { width: 1.5, color: '#ff7a45' }, symbol: 'none',
      },
      {
        name: 'MA20', type: 'line', data: ma20, xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, lineStyle: { width: 1.5, color: '#4a5ee5' }, symbol: 'none',
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: {
            color: closes[i] >= (data[i - 1]?.close ?? closes[i]) ? upColor : downColor,
          },
        })),
      },
    ],
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '4px 12px', fontSize: 12, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)' }}>{code}</span>
        {name && <span style={{ marginLeft: 6 }}>{name}</span>}
        <span style={{ float: 'right', color: 'var(--text-muted)', fontSize: 10 }}>
          {live ? '● LIVE' : ''}
        </span>
      </div>
      <div style={{ flex: 1 }}>
        <ReactECharts
          ref={chartRef}
          option={option}
          style={{ height: '100%', width: '100%' }}
          notMerge={!live}
        />
      </div>
    </div>
  );
};

export default CandlestickChart;
