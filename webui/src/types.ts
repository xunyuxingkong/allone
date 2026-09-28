export type RunStatus = 'PASS' | 'FAIL' | 'ERROR' | 'TIMEOUT' | 'INFRA_RECOVERED'
export type StepStatus = 'PASS' | 'FAIL' | 'ERROR' | 'TIMEOUT' | 'SKIPPED' | 'PENDING' | 'RUNNING'

export interface RunSummary {
  run_id: string
  started_at: string
  status: RunStatus
  database_alias: string
  git_commit: string | null
  case_count: number
  pass: number
  pass_rate: number
  fail: number
  error: number
  timeout: number
  duration_ms: number
}

export interface QueryStepReport {
  id: string
  status: StepStatus
  duration_ms: number
  columns: string[]
  column_types: (string | null)[]
  logical_types: (string | null)[]
  row_count: number | null
  result_sha256: string | null
  error_type: string | null
  error_code: string | null
  sqlstate: string | null
  error: string | null
}

export interface QueryCaseReport {
  case_id: string
  title: string | null
  feature: string | null
  tags: string[]
  source_file: string | null
  case_source_hash: string | null
  status: RunStatus | 'PENDING' | 'RUNNING'
  failure_type: string | null
  duration_ms: number
  steps: QueryStepReport[]
  error: string | null
}

export interface QueryRunReport {
  run_id: string
  started_at: string
  finished_at: string
  target: {
    database_alias: string
    host_hash: string
    sql_runtime_profile_id: string | null
    contract_set_id: string
  }
  git_commit: string | null
  cases: QueryCaseReport[]
  status: RunStatus | 'PENDING' | 'RUNNING'
}

export interface CaseDetailResponse {
  report: QueryCaseReport
  git_commit: string | null
  source_available: boolean
  case_definition: {
    metadata: { id: string; title: string; feature: string; tags: string[] }
    steps: { id: string; sql: string; comparison: { mode: string }; expected: unknown }[]
  } | null
}
