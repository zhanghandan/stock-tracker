/**
 * 排名数据状态管理
 */
import { create } from 'zustand';

export interface RankingItem {
  code: string;
  rank: number;
  name: string;
  latest_price: number | null;
  change_pct: number | null;
  composite_score: number;
  technical_score: number | null;
  sentiment_score: number | null;
  fund_flow_score: number | null;
  momentum_score: number | null;
  volume_score: number | null;
  technical_signal: string | null;
  volume_ratio: number | null;
  turnover_rate: number | null;
  pe_ttm: number | null;
  pb: number | null;
  total_mv: number | null;
  change_60d: number | null;
  scored_at: string | null;
  ai_rank?: number;
  ai_reason?: string;
  ai_risk?: string;
  ai_advice?: string;
}

interface RankingState {
  rankings: RankingItem[];
  selectedStock: RankingItem | null;
  lastUpdated: string | null;
  loading: boolean;

  setRankings: (data: RankingItem[]) => void;
  setSelectedStock: (stock: RankingItem | null) => void;
  setLastUpdated: (time: string) => void;
  setLoading: (loading: boolean) => void;
}

export const useRankingStore = create<RankingState>((set) => ({
  rankings: [],
  selectedStock: null,
  lastUpdated: null,
  loading: false,

  setRankings: (data) => set({ rankings: data }),
  setSelectedStock: (stock) => set({ selectedStock: stock }),
  setLastUpdated: (time) => set({ lastUpdated: time }),
  setLoading: (loading) => set({ loading }),
}));
