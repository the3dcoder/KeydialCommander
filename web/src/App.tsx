import { DndContext, DragOverlay, PointerSensor, useSensor, useSensors,
  type DragEndEvent, type DragStartEvent } from '@dnd-kit/core'
import { useState } from 'react'
import { useEvents } from './api/useEvents'
import { useApplyTheme } from './theme'
import { useQueryClient } from '@tanstack/react-query'
import { useStatus, usePutBinding, keys as qk } from './api/queries'
import type { ProfileBindings } from './api/types'
import { useUI } from './store'
import { ProfileBar } from './components/ProfileBar'
import { StatusStrip } from './components/StatusStrip'
import { DeviceStage } from './components/DeviceStage'
import { Inspector } from './components/Inspector'
import { ActionLibrary } from './components/ActionLibrary'
import type { Template } from './templates'

function DaemonDown() {
  return (
    <div style={{ display: 'grid', placeItems: 'center', height: '100vh', textAlign: 'center' }}>
      <div>
        <h2>Can’t reach the Keydial service</h2>
        <p className="muted">Start it with:</p>
        <p><code>systemctl --user restart huion-keydial-mini-user</code></p>
        <p className="muted">Retrying automatically…</p>
      </div>
    </div>
  )
}

export default function App() {
  useApplyTheme()
  useEvents()
  const { data: status, isError, isLoading } = useStatus()
  const put = usePutBinding(status?.active_profile || '')
  const qc = useQueryClient()
  const select = useUI((s) => s.select)
  const [dragging, setDragging] = useState<Template | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const onDragStart = (e: DragStartEvent) => {
    setDragging((e.active.data.current?.template as Template) || null)
  }
  const onDragEnd = (e: DragEndEvent) => {
    setDragging(null)
    const template = e.active.data.current?.template as Template | undefined
    const target = e.over?.id as string | undefined
    if (template && target) {
      const cached = qc.getQueryData<ProfileBindings>(qk.bindings(status?.active_profile || ''))
      if (cached?.bindings[target] &&
          !window.confirm(`${target} is already bound. Replace it?`)) {
        return
      }
      put.mutate({ actionId: target, action: template.make() })
      select(target)
    }
  }

  if (isError) return <DaemonDown />
  if (isLoading) return <div style={{ padding: 40 }} className="muted">Loading…</div>

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
      <div className="app">
        <ProfileBar />
        <div className="cols">
          <div className="lib pane"><ActionLibrary /></div>
          <div className="stage pane"><DeviceStage /></div>
          <div className="insp pane"><Inspector /></div>
        </div>
        <StatusStrip />
      </div>
      <DragOverlay>
        {dragging && (
          <div className="libcard" style={{ cursor: 'grabbing' }}>
            <span className="libic">{dragging.icon}</span>{dragging.label}
          </div>
        )}
      </DragOverlay>
    </DndContext>
  )
}
