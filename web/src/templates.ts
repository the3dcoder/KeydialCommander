import type { Action } from './api/types'

export interface Template {
  id: string
  label: string
  icon: string
  group: string
  make: () => Action
}

export const TEMPLATES: Template[] = [
  // Input
  { id: 'keystroke', label: 'Keystroke', icon: '⌨', group: 'Input',
    make: () => ({ type: 'keystroke', keys: [] }) },
  { id: 'macro', label: 'Macro', icon: '⚡', group: 'Input',
    make: () => ({ type: 'macro', steps: [{ keys: [] }] }) },
  // System
  { id: 'launch', label: 'Launch app', icon: '🚀', group: 'System',
    make: () => ({ type: 'command', argv: [''] }) },
  { id: 'url', label: 'Open URL', icon: '🌐', group: 'System',
    make: () => ({ type: 'command', argv: ['xdg-open', ''] }) },
  { id: 'command', label: 'Run command', icon: '$', group: 'System',
    make: () => ({ type: 'command', argv: [''] }) },
  // Media
  { id: 'playpause', label: 'Play / Pause', icon: '⏯', group: 'Media',
    make: () => ({ type: 'keystroke', keys: ['KEY_PLAYPAUSE'] }) },
  { id: 'volup', label: 'Volume up', icon: '🔊', group: 'Media',
    make: () => ({ type: 'keystroke', keys: ['KEY_VOLUMEUP'] }) },
  { id: 'voldown', label: 'Volume down', icon: '🔉', group: 'Media',
    make: () => ({ type: 'keystroke', keys: ['KEY_VOLUMEDOWN'] }) },
  { id: 'mute', label: 'Mute', icon: '🔇', group: 'Media',
    make: () => ({ type: 'keystroke', keys: ['KEY_MUTE'] }) },
  // Device
  { id: 'profile', label: 'Switch profile', icon: '⇄', group: 'Device',
    make: () => ({ type: 'profile_switch', profile: 'next' }) },
]
