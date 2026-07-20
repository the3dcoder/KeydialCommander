// Map a browser KeyboardEvent.code to a Linux KEY_* name.
// Some keys (e.g. Super/Meta) are unreliable to capture in Wayland browsers —
// the Inspector offers a manual picker as a fallback.

const SPECIAL: Record<string, string> = {
  Space: 'KEY_SPACE', Enter: 'KEY_ENTER', Tab: 'KEY_TAB', Backspace: 'KEY_BACKSPACE',
  Escape: 'KEY_ESC', Delete: 'KEY_DELETE', Insert: 'KEY_INSERT',
  Home: 'KEY_HOME', End: 'KEY_END', PageUp: 'KEY_PAGEUP', PageDown: 'KEY_PAGEDOWN',
  ArrowUp: 'KEY_UP', ArrowDown: 'KEY_DOWN', ArrowLeft: 'KEY_LEFT', ArrowRight: 'KEY_RIGHT',
  ControlLeft: 'KEY_LEFTCTRL', ControlRight: 'KEY_RIGHTCTRL',
  ShiftLeft: 'KEY_LEFTSHIFT', ShiftRight: 'KEY_RIGHTSHIFT',
  AltLeft: 'KEY_LEFTALT', AltRight: 'KEY_RIGHTALT',
  MetaLeft: 'KEY_LEFTMETA', MetaRight: 'KEY_RIGHTMETA',
  CapsLock: 'KEY_CAPSLOCK', NumLock: 'KEY_NUMLOCK', ScrollLock: 'KEY_SCROLLLOCK',
  Minus: 'KEY_MINUS', Equal: 'KEY_EQUAL', BracketLeft: 'KEY_LEFTBRACE',
  BracketRight: 'KEY_RIGHTBRACE', Backslash: 'KEY_BACKSLASH', Semicolon: 'KEY_SEMICOLON',
  Quote: 'KEY_APOSTROPHE', Comma: 'KEY_COMMA', Period: 'KEY_DOT', Slash: 'KEY_SLASH',
  Backquote: 'KEY_GRAVE', PrintScreen: 'KEY_PRINTSCREEN', Pause: 'KEY_PAUSE',
  ContextMenu: 'KEY_MENU',
}

export function codeToKey(code: string): string | null {
  if (SPECIAL[code]) return SPECIAL[code]
  let m = /^Key([A-Z])$/.exec(code)
  if (m) return 'KEY_' + m[1]
  m = /^Digit([0-9])$/.exec(code)
  if (m) return 'KEY_' + m[1]
  m = /^F([0-9]{1,2})$/.exec(code)
  if (m) return 'KEY_F' + m[1]
  m = /^Numpad([0-9])$/.exec(code)
  if (m) return 'KEY_KP' + m[1]
  return null
}

export const MODIFIER_KEYS = new Set([
  'KEY_LEFTCTRL', 'KEY_RIGHTCTRL', 'KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT',
  'KEY_LEFTALT', 'KEY_RIGHTALT', 'KEY_LEFTMETA', 'KEY_RIGHTMETA',
])
