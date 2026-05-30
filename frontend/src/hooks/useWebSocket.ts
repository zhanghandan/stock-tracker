/**
 * WebSocket连接Hook
 */
import { useEffect, useRef } from 'react';
import { wsClient } from '../api/websocket';
import { useRankingStore } from '../store/rankingStore';
import { useMarketStore } from '../store/marketStore';
import { useAlertStore } from '../store/alertStore';

export function useWebSocket() {
  const setRankings = useRankingStore((s) => s.setRankings);
  const setLastUpdated = useRankingStore((s) => s.setLastUpdated);
  const setMarketStatus = useMarketStore((s) => s.setMarketStatus);
  const setWsStatus = useMarketStore((s) => s.setWsStatus);
  const addAlert = useAlertStore((s) => s.addAlert);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    // 状态变化回调
    wsClient.onStatusChange = (status) => {
      setWsStatus(status);
    };

    // 排名快照
    wsClient.on('ranking_snapshot', (msg) => {
      if (msg.data) {
        setRankings(msg.data);
      }
      if (msg.timestamp) {
        setLastUpdated(msg.timestamp);
      }
    });

    // 市场状态
    wsClient.on('market_status', (msg) => {
      setMarketStatus(msg.status);
    });

    // 告警
    wsClient.on('alert', (msg) => {
      addAlert({
        level: msg.level || 'info',
        message: msg.message || '',
        code: msg.code || '',
        timestamp: msg.timestamp || new Date().toISOString(),
      });
    });

    // 个股更新
    wsClient.on('stock_update', (msg) => {
      // 更新排名中的对应股票
      useRankingStore.getState().setRankings(
        useRankingStore.getState().rankings.map((s) =>
          s.code === msg.code ? { ...s, ...msg.data } : s
        )
      );
    });

    // 连接
    wsClient.connect();

    return () => {
      wsClient.disconnect();
      initialized.current = false;
    };
  }, []);
}
