import type {
  Action, Bindings, KeyGroups, ProfileBindings, ProfileSummary, Status,
} from './types'

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  const text = await r.text()
  const body = text ? JSON.parse(text) : {}
  if (!r.ok) {
    const msg = body?.error?.message || r.statusText
    throw new Error(msg)
  }
  return body as T
}

export const api = {
  status: () => req<Status>('/api/status'),
  keys: () => req<KeyGroups>('/api/keys'),

  listProfiles: () => req<ProfileSummary[]>('/api/profiles'),
  createProfile: (name: string, clone_from?: string) =>
    req('/api/profiles', { method: 'POST', body: JSON.stringify({ name, clone_from }) }),
  renameProfile: (name: string, new_name: string) =>
    req(`/api/profiles/${encodeURIComponent(name)}`, {
      method: 'PUT', body: JSON.stringify({ new_name }),
    }),
  deleteProfile: (name: string) =>
    req(`/api/profiles/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  activateProfile: (name: string) =>
    req(`/api/profiles/${encodeURIComponent(name)}/activate`, { method: 'POST' }),

  getBindings: (name: string) =>
    req<ProfileBindings>(`/api/profiles/${encodeURIComponent(name)}/bindings`),
  putBinding: (name: string, actionId: string, action: Action) =>
    req(`/api/profiles/${encodeURIComponent(name)}/bindings/${encodeURIComponent(actionId)}`, {
      method: 'PUT', body: JSON.stringify(action),
    }),
  deleteBinding: (name: string, actionId: string) =>
    req(`/api/profiles/${encodeURIComponent(name)}/bindings/${encodeURIComponent(actionId)}`, {
      method: 'DELETE',
    }),
  setSensitivity: (name: string, dial_sensitivity: number) =>
    req(`/api/profiles/${encodeURIComponent(name)}/settings`, {
      method: 'PUT', body: JSON.stringify({ dial_sensitivity }),
    }),

  exportProfile: (name: string) =>
    fetch(`/api/profiles/${encodeURIComponent(name)}/export`).then((r) => r.text()),
  importProfile: (name: string, yaml: string) =>
    req('/api/profiles/import', { method: 'POST', body: JSON.stringify({ name, yaml }) }),

  testFire: (action: Action) =>
    req('/api/test-fire', { method: 'POST', body: JSON.stringify({ action }) }),
}

export type { Action, Bindings }
