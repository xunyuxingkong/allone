import { api } from './client'
import type { CaseDetailResponse, QueryCaseReport, QueryRunReport, RunSummary } from '../types'

export interface Page<T> {
  items: T[]
  offset: number
  limit: number
  next_offset?: number | null
  total?: number
}

export const listRuns = (params: Record<string, string | number | undefined> = {}) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== '') query.set(key, String(value))
  return api<Page<RunSummary>>(`/api/runs?${query.toString()}`)
}

export const getRun = (runId: string) => api<QueryRunReport>(`/api/runs/${encodeURIComponent(runId)}`)

export const listCases = (runId: string, params: Record<string, string | number | undefined> = {}) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== '') query.set(key, String(value))
  return api<Page<QueryCaseReport>>(`/api/runs/${encodeURIComponent(runId)}/cases?${query.toString()}`)
}

export const getCase = (runId: string, caseId: string) =>
  api<CaseDetailResponse>(`/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}`)
