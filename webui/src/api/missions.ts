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
  child_jobs: { feature: string; job_id: string; attempt: number }[]
}

export interface MissionFeatureJob {
  feature: string
  attempt: number
  job_id: string
  state: string
  mission_state?: string
  is_latest: boolean
  candidate_count: number
  generated_candidate_count: number
  case_count?: number | null
  sql_count?: number | null
  failure_count?: number | null
  coverage?: { status?: string; active_covered?: number; active_missing?: number; required?: number } | null
  approval_status: string
  ai_findings_count: number
  blockers: string[]
}

export interface AiFailureAnalysis {
  category: string
  failure_summary: string
  likely_area: string
  recommended_action: string
  confidence: number
}

export interface AiSummary {
  mission_id: string
  job_id: string | null
  available: boolean
  note?: string
  advisory_only?: boolean
  summary?: string | null
  failure_analysis?: AiFailureAnalysis | null
  generated_candidate_count?: number
  technical_review_count?: number
  technical_review_decisions?: { PASS: number; CONCERNS: number; FAIL: number }
  reused_evidence?: { reason: string | null }[]
  does_not_change_core?: boolean
}

export interface MissionView {
  mission: Mission
  state: MissionState
  requested_scope: string[]
  executed_scope: string[]
  covered_scope: string[]
  excluded_scope: string[]
  unmodelled_scope: string[]
  execution_policy: { strategy: MissionStrategy; coverage_strategy: 'pairwise' | 'all_values'; candidate_budget: number | null; data_scale: MissionDataScale; risk_focus: string[]; data_scale_applied: boolean; risk_focus_applied: boolean }
  generation_progress: { budget: number | null; generated_total: number; remaining_budget: number | null; stalled: boolean; coverage_target: string; pairwise_complete: boolean; smoke_complete: boolean; regression_pass: boolean; generated_cases_valid: boolean; no_blocking_failure: boolean; strategy_completion_frozen?: boolean }
  approval_review: { status: 'NOT_READY' | 'WAITING_APPROVAL' | 'APPROVED_CURRENT' | 'APPROVED_STALE' | 'INVALID'; reason?: string | null; readiness?: string; manifest_id?: string; plan_hash?: string; manifest_ref?: string; plan_ref?: string; candidate_count?: number; runtime_profile_id?: string; database_version?: string; database_build_time?: string; contract_bindings?: Record<string, string>; coverage?: { active_covered?: number; active_missing?: number; provisional_missing?: number }; ci_disposition?: string; technical_review_count?: number; technical_reviews?: { case_id: string | null; decision?: string; recommendation?: string; findings: string[] }[]; evidence?: { regression_status?: string; regression_failures?: number; trial_status?: string; trial_double_run_pass_count?: number; mutation_killed_count?: number; technical_review_decisions?: Record<string, number>; blockers?: string[] }; untested_scope?: string[] }
  estimate: { strategy: MissionStrategy; case_min: number; case_max: number; sql_min: number; sql_max: number; unit: string }
  feature_jobs: MissionFeatureJob[]
  feature_summary: { requested_features: number; started_features: number; completed_features: number; blocked_features: number; case_count: number; sql_count: number; failure_count: number; candidate_count: number; ai_findings_count: number }
  ai_summary: AiSummary
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
  feature_job_count?: number
  feature_jobs?: { feature: string; job_id: string | null; attempt?: number; state: string }[]
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

export const retryMissionFeature = (missionId: string, feature: string) =>
  api<MissionView>(`/api/missions/${encodeURIComponent(missionId)}/features/${encodeURIComponent(feature)}/retry`, { method: 'POST' })
