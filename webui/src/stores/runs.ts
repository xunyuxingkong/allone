import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getRun, listRuns } from '../api/runs'
import type { QueryRunReport, RunSummary } from '../types'

export const useRunsStore = defineStore('runs', () => {
  const recent = ref<RunSummary[]>([])
  const selected = ref<QueryRunReport | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function refreshRecent() {
    loading.value = true
    error.value = null
    try { recent.value = (await listRuns({ limit: 10 })).items }
    catch (cause) { error.value = cause instanceof Error ? cause.message : '无法读取运行记录' }
    finally { loading.value = false }
  }

  async function loadRun(runId: string) {
    loading.value = true
    error.value = null
    try { selected.value = await getRun(runId) }
    catch (cause) { error.value = cause instanceof Error ? cause.message : '无法读取运行详情' }
    finally { loading.value = false }
  }

  return { recent, selected, loading, error, refreshRecent, loadRun }
})
