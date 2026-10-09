import { api } from './client'

export type MissionState = 'DRAFT' | 'READY' | 'RUNNING' | 'WAITING_APPROVAL' | 'BLOCKED' | 'COMPLETED'
export type MissionStrategy = 'SMOKE' | 'STANDARD' | 'FULL' | 'AI_EXPLORATORY'
export type MissionDataScale = 'SMALL' | 'MEDIUM' | 'LARGE'

export interface Mission {
  mission_id: string
  name: string
  purpose: string
  module: 'query'
  features: string[]
  strategy: MissionStrategy
  data_scale: MissionDataScale
  risk_focus: string[]
  acceptance_goal: string
  excluded_scope: string[]
  created_by: string
  state: MissionState
  job_id: string | null
}

export interface MissionView {
  mission: Mission
  state: MissionState
  tested_scope: string[]
  untested_scope: string[]
  estimate: { strategy: MissionStrategy; case_min: number; case_max: number; sql_min: number; sql_max: number; unit: string }
  completeness_note: string
}

export interface MissionSummary {
  mission_id: string
  name: string
  state: string
  module: string
  features: string[]
  strategy: string
  job_id: string | null
  created_at: string
}

export interface MissionDefinition {
  name: string
  purpose: string
  features: string[]
  strategy: MissionStrategy
  data_scale: MissionDataScale
  risk_focus: string[]
  acceptance_goal: string
  excluded_scope: string[]
}

export const listMissions = () => api<{ items: MissionSummary[] }>('/api/missions')

export const getMission = (missionId: string) => api<MissionView>(`/api/missions/${encodeURIComponent(missionId)}`)

export const createMission = (definition: MissionDefinition) =>
  api<MissionView>('/api/missions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(definition) })

export const startMission = (missionId: string) =>
  api<MissionView>(`/api/missions/${encodeURIComponent(missionId)}/start`, { method: 'POST' })
