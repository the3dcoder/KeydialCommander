import { useState } from 'react'
import { useStatus, useProfiles, useActivateProfile, useProfileMutations } from '../api/queries'
import { useUI } from '../store'
import { Modal } from './Modal'
import { Settings } from './Settings'

export function ProfileBar() {
  const { data: profiles } = useProfiles()
  const { data: status } = useStatus()
  const activate = useActivateProfile()
  const m = useProfileMutations()
  const setTheme = useUI((s) => s.setTheme)
  const theme = useUI((s) => s.theme)
  const active = status?.active_profile
  const [creating, setCreating] = useState(false)
  const [settings, setSettings] = useState(false)
  const [name, setName] = useState('')
  const [err, setErr] = useState<string | null>(null)

  const cycleTheme = () =>
    setTheme(theme === 'system' ? 'dark' : theme === 'dark' ? 'light' : 'system')

  return (
    <div className="topbar">
      <div className="logo"><div className="mark">K</div>Keydial&nbsp;Commander</div>
      <div className="profiles">
        {(profiles || []).map((p) => (
          <button key={p.name} className={'chip' + (p.name === active ? ' active' : '')}
                  onClick={() => p.name !== active && activate.mutate(p.name)}
                  title={`${p.binding_count} bindings`}>
            {p.name}
          </button>
        ))}
        <button className="chip add" onClick={() => { setName(''); setErr(null); setCreating(true) }}>
          + New
        </button>
      </div>
      <div className="spacer" />
      <button className="iconbtn" onClick={cycleTheme} title={`Theme: ${theme}`}>
        {theme === 'system' ? '🖥' : theme === 'dark' ? '🌙' : '☀'}
      </button>
      <button className="iconbtn" onClick={() => setSettings(true)} title="Settings">⚙</button>

      {creating && (
        <Modal title="New profile" onClose={() => setCreating(false)}>
          <label className="field">Name</label>
          <input className="input" autoFocus value={name} onChange={(e) => setName(e.target.value)}
                 placeholder="e.g. Krita" onKeyDown={(e) => e.key === 'Enter' && submit()} />
          {err && <p style={{ color: 'var(--warn)', fontSize: 12 }}>{err}</p>}
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn" style={{ flex: 1 }}
                    onClick={() => create(active)}>Clone “{active}”</button>
            <button className="btn primary" style={{ flex: 1 }} onClick={() => create()}>Create empty</button>
          </div>
        </Modal>
      )}
      {settings && <Settings onClose={() => setSettings(false)} />}
    </div>
  )

  function submit() { create() }
  function create(clone?: string) {
    if (!name.trim()) { setErr('Enter a name'); return }
    m.create.mutate({ name: name.trim(), clone_from: clone },
      { onSuccess: () => { setCreating(false); activate.mutate(name.trim()) },
        onError: (e) => setErr(String(e)) })
  }
}
