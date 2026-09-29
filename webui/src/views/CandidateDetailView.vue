<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { getCandidate, trialEvidenceLabel, type CandidateDetail } from '../api/generation'

const props = defineProps<{ caseId: string }>()
const candidate = ref<CandidateDetail | null>(null)
const error = ref('')
const loading = ref(false)
let requestVersion = 0
watch(() => props.caseId, async (caseId) => {
  const version = ++requestVersion
  loading.value = true
  error.value = ''
  candidate.value = null
  try {
    const result = await getCandidate(caseId)
    if (version === requestVersion) candidate.value = result
  } catch (cause) {
    if (version === requestVersion) error.value = cause instanceof Error ? cause.message : '候选读取失败'
  } finally {
    if (version === requestVersion) loading.value = false
  }
}, { immediate: true })
const pretty = (value: unknown) => JSON.stringify(value, null, 2)
const selectionText = (item: Record<string, string>) => Object.entries(item).map(([key, value]) => `${key}=${value}`).join(' · ')
</script>

<template>
  <div class="page-heading"><div><h1>候选详情</h1><p class="mono">{{ caseId }}</p></div><RouterLink class="link" to="/candidates">← 返回候选列表</RouterLink></div>
  <div v-if="error" class="error-banner">{{ error }}</div><div v-if="loading" class="surface empty-state">正在读取候选…</div>
  <div v-if="candidate" class="detail-stack">
    <section class="surface"><h2 class="surface-title">状态与证据</h2><div class="detail-body detail-kv">
      <span class="key">生命周期状态</span><span>{{ candidate.status }}</span>
      <span class="key">人工与覆盖评审</span><span>{{ candidate.review_recorded ? '已记录' : '待评审' }}</span>
      <span class="key">试运行证据状态</span><span>{{ trialEvidenceLabel(candidate.trial_evidence_status) }}</span>
      <span class="key">Model Version</span><span>{{ candidate.coverage[0]?.model_version ?? '—' }}</span>
      <span class="key">维度组合</span><span>{{ pretty(candidate.coverage[0]?.assignment ?? {}) }}</span>
      <span class="key">Trial Artifact SHA-256</span><span class="digest">{{ candidate.validation_evidence?.trial_artifact_sha256 ?? '未记录' }}</span>
      <span class="key">Trial Result Hash</span><span class="digest">{{ candidate.validation_evidence?.trial_run_hash ?? '未记录' }}</span>
    </div></section>
    <section v-for="step in candidate.steps" :key="step.id" class="surface"><h2 class="surface-title">{{ step.id }} · SQL</h2><pre class="code-block">{{ step.sql }}</pre></section>
    <section class="surface"><h2 class="surface-title">相对正式集新增的 Pairwise 覆盖 <span class="muted">({{ candidate.coverage_contribution.new_requirements.length }})</span></h2>
      <div class="table-scroll"><table class="data-table"><thead><tr><th>组合要求</th><th>Requirement ID</th></tr></thead><tbody>
        <tr v-for="item in candidate.coverage_contribution.new_requirements" :key="item.requirement_id"><td>{{ selectionText(item.selections) }}</td><td class="mono">{{ item.requirement_id }}</td></tr>
      </tbody></table></div>
      <div v-if="!candidate.coverage_contribution.new_requirements.length" class="empty-state">该候选没有新增的 Pairwise 组合</div>
    </section>
    <section class="surface"><h2 class="surface-title">Expected</h2><pre class="code-block">{{ pretty(candidate.steps[0]?.expected ?? null) }}</pre></section>
    <section class="surface"><h2 class="surface-title">Coverage Claim</h2><pre class="code-block">{{ pretty(candidate.coverage) }}</pre></section>
    <p class="muted">试运行通过只表示技术校验完成；人工评审与晋级由现有 CLI 门禁执行。</p>
  </div>
</template>
