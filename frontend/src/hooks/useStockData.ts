/**
 * 个股数据获取Hook
 */
import { useState, useCallback } from 'react';
import apiClient from '../api/client';

export function useStockData() {
  const [loading, setLoading] = useState(false);

  const fetchStockDetail = useCallback(async (code: string) => {
    setLoading(true);
    try {
      const res = await apiClient.get(`/stocks/${code}`);
      return res.data;
    } catch (e) {
      console.error('获取股票详情失败:', e);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async (code: string, days: number = 60) => {
    try {
      const res = await apiClient.get(`/stocks/${code}/history`, { params: { days } });
      return res.data;
    } catch (e) {
      console.error('获取历史数据失败:', e);
      return null;
    }
  }, []);

  const fetchNews = useCallback(async (code: string, limit: number = 20) => {
    try {
      const res = await apiClient.get(`/stocks/${code}/news`, { params: { limit } });
      return res.data;
    } catch (e) {
      console.error('获取新闻失败:', e);
      return null;
    }
  }, []);

  const searchStock = useCallback(async (query: string) => {
    try {
      const res = await apiClient.get('/search', { params: { q: query } });
      return res.data?.items || [];
    } catch (e) {
      console.error('搜索失败:', e);
      return [];
    }
  }, []);

  return { loading, fetchStockDetail, fetchHistory, fetchNews, searchStock };
}
