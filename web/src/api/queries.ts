import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { Action } from './types'

export const keys = {
  status: ['status'] as const,
  keyList: ['keys'] as const,
  profiles: ['profiles'] as const,
  bindings: (name: string) => ['bindings', name] as const,
}

export function useStatus() {
  return useQuery({ queryKey: keys.status, queryFn: api.status, refetchInterval: 15000 })
}

export function useKeyList() {
  return useQuery({ queryKey: keys.keyList, queryFn: api.keys, staleTime: Infinity })
}

export function useProfiles() {
  return useQuery({ queryKey: keys.profiles, queryFn: api.listProfiles })
}

export function useBindings(name: string | undefined) {
  return useQuery({
    queryKey: keys.bindings(name || ''),
    queryFn: () => api.getBindings(name as string),
    enabled: !!name,
  })
}

export function useActivateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => api.activateProfile(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.profiles })
      qc.invalidateQueries({ queryKey: keys.status })
    },
  })
}

export function usePutBinding(profile: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ actionId, action }: { actionId: string; action: Action }) =>
      api.putBinding(profile, actionId, action),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.bindings(profile) })
      qc.invalidateQueries({ queryKey: keys.profiles })
    },
  })
}

export function useDeleteBinding(profile: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (actionId: string) => api.deleteBinding(profile, actionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.bindings(profile) })
      qc.invalidateQueries({ queryKey: keys.profiles })
    },
  })
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: keys.profiles })
  qc.invalidateQueries({ queryKey: keys.status })
  qc.invalidateQueries({ queryKey: ['bindings'] })
}

export function useProfileMutations() {
  const qc = useQueryClient()
  const done = () => invalidateAll(qc)
  return {
    create: useMutation({ mutationFn: (v: { name: string; clone_from?: string }) =>
      api.createProfile(v.name, v.clone_from), onSuccess: done }),
    rename: useMutation({ mutationFn: (v: { name: string; new_name: string }) =>
      api.renameProfile(v.name, v.new_name), onSuccess: done }),
    remove: useMutation({ mutationFn: (name: string) => api.deleteProfile(name), onSuccess: done }),
    importProfile: useMutation({ mutationFn: (v: { name: string; yaml: string }) =>
      api.importProfile(v.name, v.yaml), onSuccess: done }),
    setSensitivity: useMutation({ mutationFn: (v: { name: string; value: number }) =>
      api.setSensitivity(v.name, v.value), onSuccess: (_r, v) =>
        qc.invalidateQueries({ queryKey: keys.bindings(v.name) }) }),
  }
}
