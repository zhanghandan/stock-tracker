/**
 * 市场状态管理
 */
import { create } from 'zustand';

type MarketStatus = 'open' | 'lunch_break' | 'closed';
type ConnectionStatus = 'connected' | 'disconnected' | 'reconnecting';

interface MarketState {
  marketStatus: MarketStatus;
  wsStatus: ConnectionStatus;
  lastUpdate: string | null;
  reconnectAttempt: number;

  setMarketStatus: (status: MarketStatus) => void;
  setWsStatus: (status: ConnectionStatus) => void;
  setLastUpdate: (time: string) => void;
  incrementReconnect: () => void;
  resetReconnect: () => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  marketStatus: 'closed',
  wsStatus: 'disconnected',
  lastUpdate: null,
  reconnectAttempt: 0,

  setMarketStatus: (status) => set({ marketStatus: status }),
  setWsStatus: (status) => set({ wsStatus: status }),
  setLastUpdate: (time) => set({ lastUpdate: time }),
  incrementReconnect: () => set((s) => ({ reconnectAttempt: s.reconnectAttempt + 1 })),
  resetReconnect: () => set({ reconnectAttempt: 0 }),
}));
