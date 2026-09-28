import { api } from './client'

export interface RuntimeProfileView {
  sql_runtime_profile_id: string
  evidence_sha256: string
  contract_set_id: string | null
  target: Record<string, unknown>
  driver: Record<string, unknown>
  capabilities: Record<string, unknown>
}

export const getRuntimeProfile = () => api<RuntimeProfileView>('/api/runtime/profile')
export const getContract = () => api<{ contract_version: string; contract_set_id: string; descriptor_version: string }>('/api/runtime/contract')
export const getTypeSupport = () => api<{ available: boolean; items: Record<string, string | null>[] }>('/api/runtime/types')
