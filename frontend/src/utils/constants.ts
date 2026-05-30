// API基础地址
export const API_BASE = '/api';
export const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/live`;

// 信号颜色映射
export const SIGNAL_COLORS: Record<string, string> = {
  STRONG_BUY: '#cf1322',
  BUY: '#f5222d',
  HOLD: '#faad14',
  WEAK_HOLD: '#1890ff',
  SELL: '#52c41a',
};

// 信号中文
export const SIGNAL_ZH: Record<string, string> = {
  STRONG_BUY: '强烈买入',
  BUY: '买入',
  HOLD: '持有',
  WEAK_HOLD: '观望',
  SELL: '卖出',
};

// 市场状态中文
export const MARKET_STATUS_ZH: Record<string, string> = {
  open: '交易中',
  lunch_break: '午间休市',
  closed: '已收盘',
};
