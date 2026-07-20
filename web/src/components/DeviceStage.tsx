import { useEffect, useState } from 'react'
import { useDroppable } from '@dnd-kit/core'
import { useStatus, useBindings } from '../api/queries'
import { useUI } from '../store'
import { KEY_SLOTS, DIAL, bindingLabel } from '../deviceLayout'
import type { Bindings } from '../api/types'

function useRecentlyPressed(id: string): boolean {
  const ts = useUI((s) => s.pressed[id])
  const [on, setOn] = useState(false)
  useEffect(() => {
    if (!ts) return
    setOn(true)
    const t = setTimeout(() => setOn(false), 180)
    return () => clearTimeout(t)
  }, [ts])
  return on
}

function Key({ id, n, style, bindings }: {
  id: string; n: number; style: React.CSSProperties; bindings: Bindings
}) {
  const selected = useUI((s) => s.selected === id)
  const select = useUI((s) => s.select)
  const pressed = useRecentlyPressed(id)
  const { setNodeRef, isOver } = useDroppable({ id })
  const action = bindings[id]
  const label = bindingLabel(action)
  return (
    <button
      ref={setNodeRef}
      className={'key' + (selected ? ' sel' : '') + (pressed ? ' press' : '')
        + (action ? '' : ' empty') + (isOver ? ' over' : '')}
      style={style}
      onClick={() => select(id)}
      title={id}
    >
      <span className="kn">{n}</span>
      <span className="klabel">{label || '—'}</span>
    </button>
  )
}

function DialZone({ id, cls, children }: { id: string; cls: string; children: React.ReactNode }) {
  const selected = useUI((s) => s.selected === id)
  const select = useUI((s) => s.select)
  const pressed = useRecentlyPressed(id)
  const { setNodeRef, isOver } = useDroppable({ id })
  return (
    <button ref={setNodeRef}
            className={`dialbtn ${cls}` + (selected ? ' sel' : '') + (pressed ? ' press' : '')
              + (isOver ? ' over' : '')}
            onClick={() => select(id)} title={id}>
      {children}
    </button>
  )
}

export function DeviceStage() {
  const { data: status } = useStatus()
  const { data: bindingsData } = useBindings(status?.active_profile)
  const identify = useUI((s) => s.identify)
  const setIdentify = useUI((s) => s.setIdentify)
  const bindings = bindingsData?.bindings || {}
  const connected = status?.device.connected

  return (
    <>
      <div className={'device' + (connected ? '' : ' dim')}>
        <div className="dhead">
          <div className="dialwrap">
            <div className="dial">
              <DialZone id={DIAL.click} cls="dcenter">◉</DialZone>
            </div>
            <div className="dialrot">
              <DialZone id={DIAL.ccw} cls="drot">↺</DialZone>
              <DialZone id={DIAL.cw} cls="drot">↻</DialZone>
            </div>
          </div>
          <div className="brand">HUION</div>
        </div>
        <div className="keygrid">
          {KEY_SLOTS.map((k) => (
            <Key key={k.id} id={k.id} n={k.n} bindings={bindings}
                 style={{
                   gridColumn: `${k.col} / span ${k.colSpan || 1}`,
                   gridRow: `${k.row} / span ${k.rowSpan || 1}`,
                 }} />
          ))}
        </div>
      </div>

      <div className="stagefoot">
        <button className={'btn' + (identify ? ' primary' : '')}
                onClick={() => setIdentify(!identify)}>
          {identify ? 'Press a key on the device…' : '🎯 Identify a key'}
        </button>
        {!connected && <span className="muted">Device asleep — press any key to wake it</span>}
      </div>
    </>
  )
}
