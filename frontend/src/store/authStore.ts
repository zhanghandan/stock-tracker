/**
 * Auth State - Zustand
 */
import { create } from 'zustand';

interface User {
  phone: string;
  user_id: number;
  nickname: string;
  avatar?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  loggedIn: boolean;
  loading: boolean;

  setAuth: (user: User, token: string) => void;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem('token'),
  loggedIn: false,
  loading: true,

  setAuth: (user, token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    set({ user, token, loggedIn: true, loading: false });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
    set({ user: null, token: null, loggedIn: false, loading: false });
  },

  checkAuth: async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      set({ loading: false });
      return;
    }

    try {
      const res = await fetch('/api/auth/me', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.logged_in && data.user) {
        set({ user: data.user, loggedIn: true, loading: false });
      } else {
        localStorage.removeItem('token');
        set({ user: null, loggedIn: false, loading: false });
      }
    } catch {
      set({ loading: false });
    }
  },
}));
