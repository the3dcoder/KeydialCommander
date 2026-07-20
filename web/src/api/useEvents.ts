import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUI } from '../store'
import { keys } from './queries'
import type { ServerEvent } from './types'

/**
 * Connects to /api/events and routes live events into the query cache + UI store.
 * Reconnects with backoff. Returns nothing; mount once near the app root.
 */
export function useEvents() {
  const qc = useQueryClient()
  const pulse = useUI((s) => s.pulse)
  const selected = useUI.getState

  useEffect(() => {
    let ws: WebSocket | null = null
    let closed = false
    let backoff = 500

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/api/events`)

      ws.onopen = () => {
        backoff = 500
        qc.invalidateQueries({ queryKey: keys.status })
      }
      ws.onmessage = (e) => {
        let ev: ServerEvent
        try {
          ev = JSON.parse(e.data)
        } catch {
          return
        }
        if (ev.type === 'key_event') {
          if (ev.pressed) {
            pulse(ev.action_id)
            // identify mode: next press selects the control
            if (useUI.getState().identify) {
              useUI.getState().select(ev.action_id)
              useUI.getState().setIdentify(false)
            }
          }
        } else if (ev.type === 'device_state') {
          qc.invalidateQueries({ queryKey: keys.status })
        } else if (ev.type === 'profile_changed') {
          qc.invalidateQueries({ queryKey: keys.profiles })
          qc.invalidateQueries({ queryKey: keys.status })
          qc.invalidateQueries({ queryKey: ['bindings'] })
        } else if (ev.type === 'bindings_changed') {
          qc.invalidateQueries({ queryKey: keys.bindings(ev.profile) })
        }
      }
      ws.onclose = () => {
        if (closed) return
        setTimeout(connect, backoff)
        backoff = Math.min(backoff * 2, 8000)
      }
      ws.onerror = () => ws?.close()
    }

    connect()
    return () => {
      closed = true
      ws?.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  void selected
}
