/**
 * 告警消息状态
 */
import { create } from 'zustand';

export interface AlertItem {
  id: string;
  level: 'info' | 'warning' | 'critical';
  message: string;
  code: string;
  timestamp: string;
}

interface AlertState {
  alerts: AlertItem[];
  addAlert: (alert: Omit<AlertItem, 'id'>) => void;
  clearAlerts: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],

  addAlert: (alert) =>
    set((s) => ({
      alerts: [{ ...alert, id: Date.now().toString(36) }, ...s.alerts].slice(0, 100),
    })),

  clearAlerts: () => set({ alerts: [] }),
}));
