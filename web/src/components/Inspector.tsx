import { useEffect, useState } from 'react'
import { useStatus, useBindings, useProfiles, usePutBinding, useDeleteBinding } from '../api/queries'
import { api } from '../api/client'
import { useUI } from '../store'
import { ShortcutCapture } from './ShortcutCapture'
import type { Action, ActionType, MacroStep } from '../api/types'

const DEFAULTS: Record<ActionType, Action> = {
  keystroke: { type: 'keystroke', keys: [], sticky: false },
  macro: { type: 'macro', steps: [{ keys: [] }] },
  command: { type: 'command', argv: ['xdg-open', ''] },
  profile_switch: { type: 'profile_switch', profile: 'next' },
}

export function Inspector() {
  const selected = useUI((s) => s.selected)
  const { data: status } = useStatus()
  const profile = status?.active_profile
  const { data: bindingsData } = useBindings(profile)
  const { data: profiles } = useProfiles()
  const put = usePutBinding(profile || '')
  const del = useDeleteBinding(profile || '')

  const existing = selected ? bindingsData?.bindings[selected] : undefined
  const [draft, setDraft] = useState<Action>(DEFAULTS.keystroke)
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    setMsg(null)
    if (existing) setDraft(JSON.parse(JSON.stringify(existing)))
    else setDraft(DEFAULTS.keystroke)
  }, [selected, existing])

  if (!selected) {
    return <div className="muted" style={{ fontSize: 13 }}>Select a key or dial control to edit it.</div>
  }

  const setType = (t: ActionType) => setDraft(JSON.parse(JSON.stringify(DEFAULTS[t])))
  const patch = (p: Partial<Action>) => setDraft((d) => ({ ...d, ...p }))

  const save = async () => {
    try {
      await put.mutateAsync({ actionId: selected, action: draft })
      setMsg('Saved')
    } catch (e) { setMsg(String(e)) }
  }
  const clear = async () => {
    try { await del.mutateAsync(selected); setMsg('Cleared') } catch (e) { setMsg(String(e)) }
  }
  const testFire = async () => {
    try { await api.testFire(draft); setMsg('Fired') } catch (e) { setMsg(String(e)) }
  }

  return (
    <>
      <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
        Edit <span className="badge">{selected}</span>
      </h3>

      <div>
        <label className="field">Action type</label>
        <select className="input" value={draft.type} onChange={(e) => setType(e.target.value as ActionType)}>
          <option value="keystroke">Send a shortcut</option>
          <option value="macro">Run a macro</option>
          <option value="command">Launch app / run command</option>
          <option value="profile_switch">Switch profile</option>
        </select>
      </div>

      {draft.type === 'keystroke' && (
        <div>
          <label className="field">Shortcut</label>
          <ShortcutCapture value={draft.keys || []} onChange={(keys) => patch({ keys })} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 13 }}>
            <input type="checkbox" checked={!!draft.sticky} onChange={(e) => patch({ sticky: e.target.checked })} />
            Hold mode (sticky) — key stays pressed until released
          </label>
        </div>
      )}

      {draft.type === 'macro' && (
        <MacroEditor steps={draft.steps || []} onChange={(steps) => patch({ steps })} />
      )}

      {draft.type === 'command' && (
        <CommandEditor argv={draft.argv || []} onChange={(argv) => patch({ argv })} />
      )}

      {draft.type === 'profile_switch' && (
        <div>
          <label className="field">Switch to</label>
          <select className="input" value={draft.profile || 'next'} onChange={(e) => patch({ profile: e.target.value })}>
            <option value="next">Next profile (cycle)</option>
            {(profiles || []).map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
          </select>
        </div>
      )}

      <div style={{ marginTop: 'auto' }}>
        {msg && <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{msg}</div>}
        <div style={{ textAlign: 'center', marginBottom: 8 }}>
          <button className="linkbtn" onClick={testFire}>▶ Test-fire</button>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn danger" style={{ flex: 1 }} onClick={clear} disabled={!existing}>Clear</button>
          <button className="btn primary" style={{ flex: 1 }} onClick={save}>Save</button>
        </div>
      </div>
    </>
  )
}

function MacroEditor({ steps, onChange }: { steps: MacroStep[]; onChange: (s: MacroStep[]) => void }) {
  const update = (i: number, step: MacroStep) => onChange(steps.map((s, j) => (j === i ? step : s)))
  const remove = (i: number) => onChange(steps.filter((_, j) => j !== i))
  const move = (i: number, d: number) => {
    const j = i + d
    if (j < 0 || j >= steps.length) return
    const copy = steps.slice()
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
    onChange(copy)
  }
  return (
    <div>
      <label className="field">Macro steps</label>
      {steps.map((s, i) => (
        <div key={i} className="macrostep">
          <div style={{ flex: 1 }}>
            {'delay_ms' in s ? (
              <input className="input" type="number" min={0} value={s.delay_ms ?? 0}
                     onChange={(e) => update(i, { delay_ms: Number(e.target.value) })}
                     placeholder="delay (ms)" />
            ) : (
              <ShortcutCapture value={s.keys || []} onChange={(keys) => update(i, { keys })} />
            )}
          </div>
          <div className="stepbtns">
            <button className="linkbtn" onClick={() => move(i, -1)}>↑</button>
            <button className="linkbtn" onClick={() => move(i, 1)}>↓</button>
            <button className="linkbtn" onClick={() => remove(i)}>✕</button>
          </div>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
        <button className="btn" onClick={() => onChange([...steps, { keys: [] }])}>+ Key step</button>
        <button className="btn" onClick={() => onChange([...steps, { delay_ms: 100 }])}>+ Delay</button>
      </div>
    </div>
  )
}

function CommandEditor({ argv, onChange }: { argv: string[]; onChange: (a: string[]) => void }) {
  const set = (i: number, v: string) => onChange(argv.map((a, j) => (j === i ? v : a)))
  return (
    <div>
      <label className="field">Command (program + arguments)</label>
      {argv.map((a, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
          <input className="input" value={a} onChange={(e) => set(i, e.target.value)}
                 placeholder={i === 0 ? 'program (e.g. xdg-open)' : 'argument'} />
          <button className="linkbtn" onClick={() => onChange(argv.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <button className="btn" onClick={() => onChange([...argv, ''])}>+ Argument</button>
      <p className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>
        Runs directly (no shell). For a URL: <code>xdg-open</code> then the address.
      </p>
    </div>
  )
}
