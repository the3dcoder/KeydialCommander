import { useState } from 'react'
import { useDraggable } from '@dnd-kit/core'
import { TEMPLATES, type Template } from '../templates'

function Card({ t }: { t: Template }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `tpl:${t.id}`,
    data: { template: t },
  })
  const style: React.CSSProperties = {
    transform: transform ? `translate(${transform.x}px, ${transform.y}px)` : undefined,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 100 : undefined,
  }
  return (
    <div ref={setNodeRef} style={style} className="libcard" {...listeners} {...attributes}>
      <span className="libic">{t.icon}</span>
      {t.label}
    </div>
  )
}

export function ActionLibrary() {
  const [q, setQ] = useState('')
  const groups = Array.from(new Set(TEMPLATES.map((t) => t.group)))
  const filtered = (g: string) =>
    TEMPLATES.filter((t) => t.group === g && t.label.toLowerCase().includes(q.toLowerCase()))
  return (
    <div>
      <input className="input" placeholder="🔍 Search actions…" value={q}
             onChange={(e) => setQ(e.target.value)} style={{ marginBottom: 12 }} />
      {groups.map((g) => {
        const items = filtered(g)
        if (!items.length) return null
        return (
          <div key={g} style={{ marginBottom: 14 }}>
            <h4 className="libgroup">{g}</h4>
            {items.map((t) => <Card key={t.id} t={t} />)}
          </div>
        )
      })}
      <p className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>
        Drag an action onto a key — or click a key and edit it on the right.
      </p>
    </div>
  )
}
