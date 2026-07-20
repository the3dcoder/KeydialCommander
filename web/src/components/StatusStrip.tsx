import { useStatus } from '../api/queries'

export function StatusStrip() {
  const { data: status, isError } = useStatus()
  const connected = status?.device.connected
  return (
    <div className="statusstrip">
      <span className={'dot' + (connected ? ' on' : '')} />
      <span>{connected ? 'Device connected' : 'Device not connected'}</span>
      <span className="spacer" />
      {isError && <span style={{ color: 'var(--warn)' }}>daemon unreachable</span>}
      {status && <span>Keydial Commander v{status.service.version}</span>}
    </div>
  )
}
