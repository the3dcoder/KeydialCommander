import { useEffect, useRef, useState } from 'react'
import { codeToKey, MODIFIER_KEYS } from '../codeToKey'
import { useKeyList } from '../api/queries'

export function ShortcutCapture({ value, onChange }: {
  value: string[]
  onChange: (keys: string[]) => void
}) {
  const [capturing, setCapturing] = useState(false)
  const [manual, setManual] = useState(false)
  const modifiers = useRef<string[]>([])
  const { data: keyList } = useKeyList()

  const reset = () => {
    modifiers.current = []
    setCapturing(false)
  }
  const start = () => {
    modifiers.current = []
    setCapturing(true)
  }
  const finish = (keys: string[]) => {
    reset()
    onChange(keys)
  }

  useEffect(() => {
    const onWindowBlur = () => {
      modifiers.current = []
      setCapturing(false)
    }
    window.addEventListener('blur', onWindowBlur)
    return () => window.removeEventListener('blur', onWindowBlur)
  }, [])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!capturing) return
    e.preventDefault()
    if (e.repeat) return
    const main = codeToKey(e.code)
    const mods = modifiers.current
    if (main && MODIFIER_KEYS.has(main) && !mods.includes(main)) mods.push(main)
    // A modifier may already be held when this field receives focus.
    const held: [boolean, string, string][] = [
      [e.ctrlKey, 'KEY_LEFTCTRL', 'KEY_RIGHTCTRL'],
      [e.shiftKey, 'KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT'],
      [e.altKey, 'KEY_LEFTALT', 'KEY_RIGHTALT'],
      [e.metaKey, 'KEY_LEFTMETA', 'KEY_RIGHTMETA'],
    ]
    for (const [pressed, left, right] of held) {
      if (pressed && !mods.includes(left) && !mods.includes(right)) mods.push(left)
    }
    if (main && !MODIFIER_KEYS.has(main)) {
      finish([...mods, main])
    }
  }

  const onKeyUp = (e: React.KeyboardEvent) => {
    if (!capturing) return
    e.preventDefault()
    const key = codeToKey(e.code)
    if (key && MODIFIER_KEYS.has(key) && modifiers.current.includes(key)) {
      finish([...modifiers.current])
    }
  }

  const label = value.length
    ? value.map((k) => k.replace(/^KEY_/, '')).join(' + ')
    : capturing ? 'Press a shortcut…' : 'Click to capture'

  return (
    <div>
      <div
        tabIndex={0}
        className="capture"
        onFocus={start}
        onClick={start}
        onBlur={reset}
        onKeyDown={onKeyDown}
        onKeyUp={onKeyUp}
        style={{ outline: capturing ? '2px solid var(--accent)' : undefined }}
      >
        {label}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
        <button className="linkbtn" onClick={() => setManual(!manual)}>
          {manual ? 'hide manual picker' : 'pick manually'}
        </button>
        {value.length > 0 && (
          <button className="linkbtn" onClick={() => finish([])}>clear keys</button>
        )}
      </div>
      {manual && keyList && (
        <select
          className="input"
          style={{ marginTop: 6 }}
          onChange={(e) => {
            if (e.target.value) onChange([...value, e.target.value])
          }}
          value=""
        >
          <option value="">+ add a key…</option>
          {Object.entries(keyList.groups).map(([g, ks]) => (
            <optgroup key={g} label={g}>
              {ks.map((k) => <option key={k} value={k}>{k}</option>)}
            </optgroup>
          ))}
        </select>
      )}
    </div>
  )
}
