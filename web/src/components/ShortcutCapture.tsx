import { useState } from 'react'
import { codeToKey, MODIFIER_KEYS } from '../codeToKey'
import { useKeyList } from '../api/queries'

export function ShortcutCapture({ value, onChange }: {
  value: string[]
  onChange: (keys: string[]) => void
}) {
  const [capturing, setCapturing] = useState(false)
  const [manual, setManual] = useState(false)
  const { data: keyList } = useKeyList()

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!capturing) return
    e.preventDefault()
    const mods: string[] = []
    if (e.ctrlKey) mods.push('KEY_LEFTCTRL')
    if (e.shiftKey) mods.push('KEY_LEFTSHIFT')
    if (e.altKey) mods.push('KEY_LEFTALT')
    if (e.metaKey) mods.push('KEY_LEFTMETA')
    const main = codeToKey(e.code)
    if (main && !MODIFIER_KEYS.has(main)) {
      onChange([...mods, main])
      setCapturing(false)
    } else if (main && MODIFIER_KEYS.has(main)) {
      // pressing only a modifier: capture the modifier itself
      onChange([main])
      setCapturing(false)
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
        onFocus={() => setCapturing(true)}
        onBlur={() => setCapturing(false)}
        onKeyDown={onKeyDown}
        style={{ outline: capturing ? '2px solid var(--accent)' : undefined }}
      >
        {label}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
        <button className="linkbtn" onClick={() => setManual(!manual)}>
          {manual ? 'hide manual picker' : 'pick manually'}
        </button>
        {value.length > 0 && (
          <button className="linkbtn" onClick={() => onChange([])}>clear keys</button>
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
