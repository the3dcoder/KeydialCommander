import { useStatus } from '../api/queries'

export function StatusStrip() {
  const { data: status, isError } = useStatus()
  const connected = status?.device.connected
  const state = status?.device.state
  const ready = connected && status?.device.ready !== false && status?.output?.available !== false
  const recoveryMessages: Record<string, string> = {
    release_controls: 'Release controls to resume',
    recovering: 'Recovering device input',
    missing_input: 'Waiting for all K20 controls',
    capture_failed: 'Cannot access K20 input',
    output_unavailable: 'Output unavailable — restart Commander after resolving the cause',
    stopped: 'Commander stopped',
  }
  const message = (status?.output?.available === false ? recoveryMessages.output_unavailable :
    (state && recoveryMessages[state])) || (connected ? 'Device connected' : 'Device not connected')
  return (
    <div className="statusstrip">
      <span className={'dot' + (ready ? ' on' : '')} />
      <span role="status">{message}</span>
      <span className="spacer" />
      {isError && <span style={{ color: 'var(--warn)' }}>daemon unreachable</span>}
      {status && <span>Keydial Commander v{status.service.version}</span>}
    </div>
  )
}
