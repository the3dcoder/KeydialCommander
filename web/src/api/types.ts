export type ActionType = 'keystroke' | 'macro' | 'command' | 'profile_switch'

export interface MacroStep {
  keys?: string[]
  delay_ms?: number
}

export interface Action {
  type: ActionType
  keys?: string[] | null
  sticky?: boolean
  steps?: MacroStep[] | null
  argv?: string[] | null
  profile?: string | null
  description?: string | null
}

export type Bindings = Record<string, Action>

export interface ProfileSummary {
  name: string
  binding_count: number
  active: boolean
}

export interface ProfileBindings {
  bindings: Bindings
  dial_sensitivity: number
}

export interface Status {
  device: { connected: boolean }
  service: { version: string }
  active_profile: string
}

export interface KeyGroups {
  groups: Record<string, string[]>
  all: string[]
}

// WebSocket event shapes
export type ServerEvent =
  | { type: 'key_event'; action_id: string; pressed: boolean }
  | { type: 'device_state'; connected: boolean; battery: number | null }
  | { type: 'profile_changed'; name: string }
  | { type: 'bindings_changed'; profile: string }
