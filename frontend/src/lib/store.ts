import { create } from 'zustand';
import type { Device, Event } from '@/types';

interface AppState {
  wsConnected: boolean;
  setWsConnected: (v: boolean) => void;

  // Live device states (updated via WS)
  deviceStates: Record<string, Record<string, any>>;
  updateDeviceState: (deviceId: string, state: Record<string, any>) => void;

  // Recent events (ring buffer, max 500)
  recentEvents: Event[];
  addEvent: (event: Event) => void;
  clearEvents: () => void;

  // UI state
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

export const useStore = create<AppState>((set) => ({
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  deviceStates: {},
  updateDeviceState: (deviceId, state) =>
    set((s) => ({
      deviceStates: { ...s.deviceStates, [deviceId]: state },
    })),

  recentEvents: [],
  addEvent: (event) =>
    set((s) => ({
      recentEvents: [event, ...s.recentEvents].slice(0, 500),
    })),
  clearEvents: () => set({ recentEvents: [] }),

  theme: (typeof window !== 'undefined' && localStorage.getItem('sds-theme') === 'dark') ? 'dark' : 'light',
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === 'light' ? 'dark' : 'light';
      localStorage.setItem('sds-theme', next);
      document.documentElement.classList.toggle('dark', next === 'dark');
      return { theme: next };
    }),
}));
