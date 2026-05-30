/**
 * 格式化工具函数
 */

// 价格格式化
export function formatPrice(price: number | null | undefined): string {
  if (price == null) return '-';
  return price.toFixed(2);
}

// 涨跌幅格式化
export function formatChangePct(pct: number | null | undefined): string {
  if (pct == null) return '-';
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
}

// 大数值格式化
export function formatBigNumber(num: number | null | undefined): string {
  if (num == null) return '-';
  if (Math.abs(num) >= 1e12) {
    return (num / 1e12).toFixed(2) + '万亿';
  }
  if (Math.abs(num) >= 1e8) {
    return (num / 1e8).toFixed(2) + '亿';
  }
  if (Math.abs(num) >= 1e4) {
    return (num / 1e4).toFixed(2) + '万';
  }
  return num.toFixed(2);
}

// 成交量格式化
export function formatVolume(vol: number | null | undefined): string {
  if (vol == null) return '-';
  if (vol >= 1e8) return (vol / 1e8).toFixed(2) + '亿手';
  if (vol >= 1e4) return (vol / 1e4).toFixed(2) + '万手';
  return vol.toFixed(0);
}

// 评分颜色
export function getScoreColor(score: number): string {
  if (score >= 75) return '#cf1322';
  if (score >= 65) return '#f5222d';
  if (score >= 45) return '#faad14';
  if (score >= 30) return '#1890ff';
  return '#52c41a';
}

// 涨跌颜色CSS类
export function changeColorClass(pct: number | null | undefined): string {
  if (pct == null) return '';
  if (pct > 0) return 'up';
  if (pct < 0) return 'down';
  return '';
}

// 时间格式化
export function formatTime(isoStr: string | null | undefined): string {
  if (!isoStr) return '-';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoStr;
  }
}

// PE格式化
export function formatPE(pe: number | null | undefined): string {
  if (pe == null) return '-';
  if (pe < 0) return '亏损';
  return pe.toFixed(2);
}
