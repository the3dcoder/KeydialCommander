import { create } from 'zustand'

export type Theme = 'system' | 'light' | 'dark'

interface UIState {
  // currently selected control (action_id) in the DeviceStage, or null
  selected: string | null
  select: (id: string | null) => void

  // identify mode: next physical press selects that control
  identify: boolean
  setIdentify: (on: boolean) => void

  // live pulse: action_id -> timestamp of last press (for highlight animation)
  pressed: Record<string, number>
  pulse: (id: string) => void

  theme: Theme
  setTheme: (t: Theme) => void
}

export const useUI = create<UIState>((set) => ({
  selected: null,
  select: (id) => set({ selected: id }),

  identify: false,
  setIdentify: (on) => set({ identify: on }),

  pressed: {},
  pulse: (id) => set((s) => ({ pressed: { ...s.pressed, [id]: Date.now() } })),

  theme: (localStorage.getItem('kc-theme') as Theme) || 'system',
  setTheme: (t) => {
    localStorage.setItem('kc-theme', t)
    set({ theme: t })
  },
}))
