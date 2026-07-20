import { useState } from 'react'
import { Modal } from './Modal'
import { useStatus, useBindings, useProfiles, useProfileMutations } from '../api/queries'
import { api } from '../api/client'
import { useUI, type Theme } from '../store'

export function Settings({ onClose }: { onClose: () => void }) {
  const { data: status } = useStatus()
  const profile = status?.active_profile || ''
  const { data: bindings } = useBindings(profile)
  const { data: profiles } = useProfiles()
  const m = useProfileMutations()
  const theme = useUI((s) => s.theme)
  const setTheme = useUI((s) => s.setTheme)
  const [rename, setRename] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const sensitivity = bindings?.dial_sensitivity ?? 1.0

  const doExport = async () => {
    const yaml = await api.exportProfile(profile)
    const blob = new Blob([yaml], { type: 'application/x-yaml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${profile}.yaml`; a.click()
    URL.revokeObjectURL(url)
  }
  const doImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = () => {
      const name = f.name.replace(/\.ya?ml$/i, '')
      m.importProfile.mutate({ name, yaml: String(reader.result) },
        { onError: (err) => setMsg(String(err)) })
    }
    reader.readAsText(f)
  }

  return (
    <Modal title="Settings" onClose={onClose}>
      <section className="setsec">
        <h4>Dial sensitivity</h4>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <input type="range" min={0.25} max={4} step={0.25} defaultValue={sensitivity}
                 style={{ flex: 1 }}
                 onChange={(e) => m.setSensitivity.mutate({ name: profile, value: Number(e.target.value) })} />
          <span className="muted">{sensitivity.toFixed(2)}×</span>
        </div>
        <p className="muted" style={{ fontSize: 11.5 }}>Lower = slower dial, higher = faster (per profile).</p>
      </section>

      <section className="setsec">
        <h4>Theme</h4>
        <select className="input" value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
          <option value="system">Follow system</option>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </section>

      <section className="setsec">
        <h4>Profile: {profile}</h4>
        <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
          <input className="input" placeholder="Rename to…" value={rename}
                 onChange={(e) => setRename(e.target.value)} />
          <button className="btn" disabled={!rename}
                  onClick={() => rename && m.rename.mutate({ name: profile, new_name: rename },
                    { onSuccess: () => setRename(''), onError: (e) => setMsg(String(e)) })}>
            Rename
          </button>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button className="btn" onClick={() => m.create.mutate({ name: `${profile} copy`, clone_from: profile },
            { onError: (e) => setMsg(String(e)) })}>Duplicate</button>
          <button className="btn" onClick={doExport}>Export</button>
          <label className="btn" style={{ cursor: 'pointer' }}>
            Import<input type="file" accept=".yaml,.yml" hidden onChange={doImport} />
          </label>
          <button className="btn danger" disabled={(profiles?.length ?? 0) <= 1}
                  onClick={() => m.remove.mutate(profile, { onError: (e) => setMsg(String(e)) })}>
            Delete
          </button>
        </div>
        {msg && <p style={{ color: 'var(--warn)', fontSize: 12 }}>{msg}</p>}
      </section>

      <section className="setsec">
        <h4>About</h4>
        <p className="muted" style={{ fontSize: 12.5 }}>
          Keydial Commander v{status?.service.version} — evdev driver for the Huion Keydial Mini (K20).
        </p>
      </section>
    </Modal>
  )
}
