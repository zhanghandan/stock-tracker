/**
 * K线图 + MA均线 + 成交量 - ECharts
 */
import React, { useEffect, useState, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin, Empty } from 'antd';
import apiClient from '../api/client';

interface Props {
  code: string;
  name: string;
  height?: number;
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

const CandlestickChart: React.FC<Props> = ({ code, name, height = 400 }) => {
  const [data, setData] = useState<KLineData[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get(`/stocks/${code}/history`, { params: { days: 60 } });
      if (res.data?.data) {
        setData(res.data.data);
      }
    } catch (e) {
      console.error('获取K线失败:', e);
    } finally {
      setLoading(false);
    }
  }, [code]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <Spin tip="加载K线数据..." style={{ display: 'block', textAlign: 'center', padding: 40 }} />;
  if (!data.length) return <Empty description="暂无K线数据" />;

  const dates = data.map((d) => d.trade_date);
  const ohlc = data.map((d) => [d.open, d.close, d.low, d.high]);
  const volumes = data.map((d) => d.volume);
  const closes = data.map((d) => d.close);

  // 计算MA5, MA10, MA20
  const calcMA = (period: number) => {
    return closes.map((_, i) => {
      if (i < period - 1) return null;
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += closes[j];
      return +(sum / period).toFixed(2);
    });
  };

  const ma5 = calcMA(5);
  const ma10 = calcMA(10);
  const ma20 = calcMA(20);

  const upColor = '#cf1322';
  const downColor = '#52c41a';

  const option = {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA20'],
      top: 0,
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
        axisLine: { onZero: false },
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLabel: {
          rotate: 45,
          fontSize: 10,
          formatter: (v: string) => v.slice(5), // MM-DD
        },
      },
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        splitArea: { show: true },
        axisLabel: { fontSize: 10 },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: {
          fontSize: 10,
          formatter: (v: number) => v >= 1e8 ? (v / 1e8).toFixed(1) + '亿' : (v / 1e4).toFixed(0) + '万',
        },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 50, end: 100, bottom: 5 },
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
        name: 'MA5',
        type: 'line',
        data: ma5,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        lineStyle: { width: 1, color: '#ffc53d' },
        symbol: 'none',
      },
      {
        name: 'MA10',
        type: 'line',
        data: ma10,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        lineStyle: { width: 1, color: '#ff7a45' },
        symbol: 'none',
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        lineStyle: { width: 1, color: '#597ef7' },
        symbol: 'none',
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: {
            color: closes[i] >= (data[i - 1]?.close ?? closes[i]) ? upColor : downColor,
          },
        })),
        xAxisIndex: 1,
        yAxisIndex: 1,
      },
    ],
  };

  return (
    <div>
      <h3 style={{ margin: '0 0 8px 0' }}>
        {name}({code}) - K线图
      </h3>
      <ReactECharts option={option} style={{ height }} notMerge />
    </div>
  );
};

export default CandlestickChart;
