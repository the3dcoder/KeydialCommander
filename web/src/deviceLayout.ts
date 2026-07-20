import type { Action } from './api/types'

// Physical layout of the K20 as a 4-column grid (buttons 1..18) plus the dial.
// Kept as data so the arrangement is easy to correct against the hardware.
// (row/col are 1-indexed grid positions; span optional.)
export interface KeySlot {
  id: string        // action_id, e.g. "BUTTON_1"
  n: number         // physical number shown on the key
  col: number
  row: number
  colSpan?: number
  rowSpan?: number
}

export const KEY_SLOTS: KeySlot[] = [
  { id: 'BUTTON_1', n: 1, col: 1, row: 1 },
  { id: 'BUTTON_2', n: 2, col: 2, row: 1 },
  { id: 'BUTTON_3', n: 3, col: 3, row: 1 },
  { id: 'BUTTON_4', n: 4, col: 4, row: 1 },
  { id: 'BUTTON_5', n: 5, col: 1, row: 2 },
  { id: 'BUTTON_6', n: 6, col: 2, row: 2 },
  { id: 'BUTTON_7', n: 7, col: 3, row: 2 },
  { id: 'BUTTON_8', n: 8, col: 4, row: 2 },
  { id: 'BUTTON_9', n: 9, col: 1, row: 3 },
  { id: 'BUTTON_10', n: 10, col: 2, row: 3 },
  { id: 'BUTTON_11', n: 11, col: 3, row: 3 },
  { id: 'BUTTON_12', n: 12, col: 4, row: 3 },
  { id: 'BUTTON_13', n: 13, col: 1, row: 4 },
  { id: 'BUTTON_14', n: 14, col: 2, row: 4 },
  { id: 'BUTTON_15', n: 15, col: 3, row: 4 },
  { id: 'BUTTON_16', n: 16, col: 4, row: 4, rowSpan: 2 },
  { id: 'BUTTON_17', n: 17, col: 1, row: 5, colSpan: 2 },
  { id: 'BUTTON_18', n: 18, col: 3, row: 5 },
]

export const DIAL = {
  cw: 'DIAL_CW',
  ccw: 'DIAL_CCW',
  click: 'DIAL_CLICK',
}

/** Short human label for a bound action, for display on a key. */
export function bindingLabel(a: Action | undefined): string {
  if (!a) return ''
  switch (a.type) {
    case 'keystroke':
      return (a.keys || []).map(shortKey).join('+') + (a.sticky ? ' ⏸' : '')
    case 'macro':
      return `Macro (${(a.steps || []).length})`
    case 'command':
      return (a.argv || [])[0] ? `▶ ${basename((a.argv || [])[0])}` : 'Command'
    case 'profile_switch':
      return `⇄ ${a.profile}`
    default:
      return ''
  }
}

function shortKey(k: string): string {
  return k.replace(/^KEY_/, '').replace(/^BTN_/, '')
    .replace('LEFTCTRL', 'Ctrl').replace('RIGHTCTRL', 'Ctrl')
    .replace('LEFTSHIFT', 'Shift').replace('RIGHTSHIFT', 'Shift')
    .replace('LEFTALT', 'Alt').replace('RIGHTALT', 'Alt')
    .replace('LEFTMETA', 'Super').replace('RIGHTMETA', 'Super')
}

function basename(p: string): string {
  const parts = p.split(/[/\\]/)
  return parts[parts.length - 1]
}
