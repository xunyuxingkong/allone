import { api } from './client'

export interface CoverageRequirement {
  requirement_id: string
  selections: Record<string, string>
  candidate_case_ids: string[]
}

export interface CoverageView {
  model_id: string
  model_version: string
  strategy: 'pairwise' | 'all_values'
  required: number
  active_covered: number
  active_missing: number
  missing_requirements: CoverageRequirement[]
  review_candidate_count: number
  provisional_covered: number
  provisional_missing: number
  matrix: {
    dimensions: string[]
    required: number
    active_covered: number
    provisional_covered: number
  }[]
  dimensions: Record<string, string[]>
  constraints: Record<string, unknown>[]
}

export interface CandidateSummary {
  case_id: string
  status: string
  assignment: Record<string, string>
  model_version: string | null
  trial_verified: boolean
  trial_evidence_status: string
  review_recorded: boolean
}

export interface CandidateDetail {
  case_id: string
  status: string
  coverage: { assignment: Record<string, string>; model_id: string; model_version: string }[]
  generation: Record<string, unknown> | null
  steps: { id: string; sql: string; expected: unknown; comparison: unknown }[]
  validation_evidence: Record<string, string> | null
  mutation_evidence: Record<string, unknown> | null
  oracle: Record<string, unknown> | null
  review_evidence: Record<string, unknown> | null
  coverage_review: Record<string, unknown> | null
  review_binding_status: string
  trial_evidence_status: string
  review_recorded: boolean
  coverage_contribution: {
    strategy: 'pairwise'
    new_requirements: Pick<CoverageRequirement, 'requirement_id' | 'selections'>[]
  }
}

export const getCoverage = (strategy: 'pairwise' | 'all_values' = 'pairwise') =>
  api<CoverageView>(`/api/coverage?strategy=${strategy}`)
export const getCandidates = (status?: string) =>
  api<{ items: CandidateSummary[]; total: number }>(`/api/candidates${status ? `?status=${encodeURIComponent(status)}` : ''}`)
export const getCandidate = (caseId: string) =>
  api<CandidateDetail>(`/api/candidates/${encodeURIComponent(caseId)}`)

export interface TrialRowsPage {
  case_id: string
  run: 'run1' | 'run2'
  step_id: string
  columns: string[]
  column_types: string[]
  row_count: number
  offset: number
  limit: number
  rows: unknown[][]
  result_sha256: string
}

export const getTrialRows = (caseId: string, run: 'run1' | 'run2', stepId: string, offset = 0, limit = 50) =>
  api<TrialRowsPage>(`/api/candidates/${encodeURIComponent(caseId)}/trial-rows?run=${run}&step_id=${encodeURIComponent(stepId)}&offset=${offset}&limit=${limit}`)

const trialEvidenceLabels: Record<string, string> = {
  verified: '已核验', missing: '未试运行', profile_unconfigured: '待配置 Profile',
  contract_stale: '契约已变化', profile_stale: 'Profile 已变化', hash_mismatch: '哈希不符',
  candidate_changed: '候选已变化', artifact_unavailable: '制品不可用',
  artifact_invalid: '制品无效', invalid_reference: '引用无效',
}
export const trialEvidenceLabel = (status: string) => trialEvidenceLabels[status] ?? status
