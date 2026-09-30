<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { getCandidate, getTrialRows, trialEvidenceLabel, type CandidateDetail, type TrialRowsPage } from '../api/generation'

const props = defineProps<{ caseId: string }>()
const candidate = ref<CandidateDetail | null>(null)
const error = ref('')
const loading = ref(false)
const rowPages = ref<Record<string, TrialRowsPage>>({})
const rowErrors = ref<Record<string, string>>({})
let requestVersion = 0
const rowKey = (run: string, stepId: string) => `${run}:${stepId}`
const emptyPage: TrialRowsPage = { case_id: '', run: 'run1', step_id: '', columns: [], column_types: [], row_count: 0, offset: 0, limit: 50, rows: [], result_sha256: '' }
const rowPage = (run: string, stepId: string) => rowPages.value[rowKey(run, stepId)] ?? emptyPage
async function loadRows(run: 'run1' | 'run2', stepId: string, offset = 0) {
  const key = rowKey(run, stepId)
  const version = requestVersion
  const caseId = props.caseId
  try {
    const page = await getTrialRows(caseId, run, stepId, offset)
    if (version !== requestVersion) return
    rowPages.value[key] = page
    rowErrors.value[key] = ''
  } catch (cause) {
    if (version !== requestVersion) return
    rowErrors.value[key] = cause instanceof Error ? cause.message : '原始行读取失败'
  }
}
watch(() => props.caseId, async (caseId) => {
  const version = ++requestVersion
  loading.value = true
  error.value = ''
  candidate.value = null
  rowPages.value = {}
  rowErrors.value = {}
  try {
    const result = await getCandidate(caseId)
    if (version === requestVersion) {
      candidate.value = result
      await Promise.all(result.steps.flatMap(step => [loadRows('run1', step.id), loadRows('run2', step.id)]))
    }
  } catch (cause) {
    if (version === requestVersion) error.value = cause instanceof Error ? cause.message : '候选读取失败'
  } finally {
    if (version === requestVersion) loading.value = false
  }
}, { immediate: true })
const pretty = (value: unknown) => JSON.stringify(value, null, 2)
const selectionText = (item: Record<string, string>) => Object.entries(item).map(([key, value]) => `${key}=${value}`).join(' · ')
const artifactUrl = (kind: 'trial' | 'mutation') => `/api/candidates/${encodeURIComponent(props.caseId)}/artifacts/${kind}`
</script>

<template>
  <div class="page-heading"><div><h1>候选详情</h1><p class="mono">{{ caseId }}</p></div><RouterLink class="link" to="/candidates">← 返回候选列表</RouterLink></div>
  <div v-if="error" class="error-banner">{{ error }}</div><div v-if="loading" class="surface empty-state">正在读取候选…</div>
  <div v-if="candidate" class="detail-stack">
    <section class="surface"><h2 class="surface-title">状态与证据</h2><div class="detail-body detail-kv">
      <span class="key">生命周期状态</span><span>{{ candidate.status }}</span>
      <span class="key">评审绑定状态</span><span>{{ candidate.review_binding_status === 'binding_valid' ? '记录与当前输入一致；仍需核实批准者' : candidate.review_binding_status === 'missing' ? '待评审' : '评审记录已过期或无效' }}</span>
      <span class="key">试运行证据状态</span><span>{{ trialEvidenceLabel(candidate.trial_evidence_status) }}</span>
      <span class="key">Model Version</span><span>{{ candidate.coverage[0]?.model_version ?? '—' }}</span>
      <span class="key">维度组合</span><span>{{ pretty(candidate.coverage[0]?.assignment ?? {}) }}</span>
      <span class="key">Trial Artifact SHA-256</span><span class="digest">{{ candidate.validation_evidence?.trial_artifact_sha256 ?? '未记录' }}</span>
      <span class="key">Trial Result Hash</span><span class="digest">{{ candidate.validation_evidence?.trial_run_hash ?? '未记录' }}</span>
    </div></section>
    <section v-for="step in candidate.steps" :key="step.id" class="surface">
      <h2 class="surface-title">{{ step.id }} · SQL / Expected / Xugu 原始结果</h2>
      <pre class="code-block">{{ step.sql }}</pre>
      <div class="detail-body"><h3>Expected</h3><pre class="code-block">{{ pretty(step.expected) }}</pre><p class="muted">比较方式：{{ pretty(step.comparison) }}</p></div>
      <div v-for="run in (['run1', 'run2'] as const)" :key="run" class="detail-body">
        <h3>{{ run }} · 实际结果</h3>
        <p v-if="rowErrors[rowKey(run, step.id)]" class="error-banner">{{ rowErrors[rowKey(run, step.id)] }}</p>
        <template v-if="rowPages[rowKey(run, step.id)]">
          <p class="muted">共 {{ rowPage(run, step.id).row_count }} 行；当前显示 {{ rowPage(run, step.id).rows.length ? rowPage(run, step.id).offset + 1 : 0 }}–{{ Math.min(rowPage(run, step.id).offset + rowPage(run, step.id).rows.length, rowPage(run, step.id).row_count) }} 行</p>
          <pre class="code-block">{{ pretty({ columns: rowPage(run, step.id).columns, column_types: rowPage(run, step.id).column_types, rows: rowPage(run, step.id).rows }) }}</pre>
          <button :disabled="rowPage(run, step.id).offset === 0" @click="loadRows(run, step.id, Math.max(0, rowPage(run, step.id).offset - 50))">上一页</button>
          <button :disabled="rowPage(run, step.id).offset + 50 >= rowPage(run, step.id).row_count" @click="loadRows(run, step.id, rowPage(run, step.id).offset + 50)">下一页</button>
        </template>
      </div>
    </section>
    <section class="surface"><h2 class="surface-title">相对正式集新增的 Pairwise 覆盖 <span class="muted">({{ candidate.coverage_contribution.new_requirements.length }})</span></h2>
      <div class="table-scroll"><table class="data-table"><thead><tr><th>组合要求</th><th>Requirement ID</th></tr></thead><tbody>
        <tr v-for="item in candidate.coverage_contribution.new_requirements" :key="item.requirement_id"><td>{{ selectionText(item.selections) }}</td><td class="mono">{{ item.requirement_id }}</td></tr>
      </tbody></table></div>
      <div v-if="!candidate.coverage_contribution.new_requirements.length" class="empty-state">该候选没有新增的 Pairwise 组合</div>
    </section>
    <section class="surface"><h2 class="surface-title">完整证据</h2><div class="detail-body">
      <p><a class="link" :href="artifactUrl('trial')">下载完整 Trial JSON</a> · <a class="link" :href="artifactUrl('mutation')">下载 Mutation JSON</a></p>
      <h3>Oracle</h3><pre class="code-block">{{ pretty(candidate.oracle) }}</pre>
      <h3>Mutation Evidence</h3><pre class="code-block">{{ pretty(candidate.mutation_evidence) }}</pre>
      <h3>Review Evidence</h3><pre class="code-block">{{ pretty(candidate.review_evidence) }}</pre>
      <h3>Coverage Review</h3><pre class="code-block">{{ pretty(candidate.coverage_review) }}</pre>
    </div></section>
    <section class="surface"><h2 class="surface-title">Coverage Claim</h2><pre class="code-block">{{ pretty(candidate.coverage) }}</pre></section>
    <p class="muted">试运行通过只表示技术校验完成；人工评审与晋级由现有 CLI 门禁执行。</p>
  </div>
</template>

<style scoped>
.detail-stack { grid-template-columns: minmax(0, 1fr); min-width: 0; }
.detail-stack > .surface { min-width: 0; }
.detail-kv > span, .detail-body > .muted { overflow-wrap: anywhere; }
.table-scroll { overflow-x: auto; }
</style>
