<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
import StructuredTable from '../components/StructuredTable.vue'
type Result = { action: string; status: string; case_id?: string; blockers: string[]; evidence_refs: string[]; outputs: Record<string, unknown> }
type Job = { job_id: string; plan: { goal: string }; state: string; revision: number; blockers: string[]; explanation: string; current_action?: { action: string }; action_results: Result[]; failure_analysis?: Record<string, unknown> }
const props = defineProps<{ jobId: string }>()
const job = ref<Job | null>(null)
const error = ref('')
const loading = ref(false)
let generation = 0
async function refresh() {
  const current = ++generation
  loading.value = true; error.value = ''; job.value = null
  try { const value = await api<Job>(`/api/jobs/${encodeURIComponent(props.jobId)}`); if (current === generation) job.value = value }
  catch (cause) { if (current === generation) error.value = cause instanceof Error ? cause.message : '任务读取失败' }
  finally { if (current === generation) loading.value = false }
}
watch(() => props.jobId, refresh, { immediate: true })
</script>

<template>
  <div class="page-heading"><div><RouterLink class="link" to="/jobs">← 测试任务</RouterLink><h1>任务详情</h1></div><button class="control refresh-button" :disabled="loading" @click="refresh">刷新</button></div>
  <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
  <p v-if="loading" class="empty-state">正在读取任务…</p>
  <template v-if="job">
    <section class="surface job-section"><h2>{{ job.plan.goal }}</h2><p>状态：<strong>{{ job.state }}</strong> · 记录版本：{{ job.revision }}</p><p v-if="job.current_action">正在执行：{{ job.current_action.action }}</p>
      <p>AI 技术评审与人工批准分别记录。单个任务完成不代表 Query 全模块验收完成。</p>
      <div v-if="job.blockers.length" class="error-banner"><strong>待处理事项</strong><ul><li v-for="item in job.blockers" :key="item">{{ item }}</li></ul></div>
    </section>
    <section v-if="job.explanation || job.failure_analysis" class="surface job-section ai-section">
      <h2>AI 测试分析</h2>
      <p v-if="job.explanation" class="narrative">{{ job.explanation }}</p>
      <p v-else class="muted">本轮尚未产生 AI 分析文本。</p>
      <div v-if="job.failure_analysis" class="failure-box">
        <b>AI 失败分析（建议）</b>
        <StructuredTable :value="job.failure_analysis" />
      </div>
      <p class="hint">以上为 AI 建议，不改变 Core 判定；PASS/FAIL、覆盖与验收仍由 Core 决定。</p>
    </section>
    <section class="surface job-section"><h2>动作记录</h2><p v-if="!job.action_results.length">等待 Agent 选择下一步动作。</p>
      <details v-for="(result, index) in job.action_results" :key="index"><summary>{{ index + 1 }}. {{ result.action }} · {{ result.status }} {{ result.case_id || '' }}</summary>
        <p v-if="result.case_id"><RouterLink class="link" :to="`/candidates/${result.case_id}`">查看候选与原始结果</RouterLink></p>
        <ul v-if="result.blockers.length"><li v-for="blocker in result.blockers" :key="blocker">{{ blocker }}</li></ul>
        <p v-for="evidence in result.evidence_refs" :key="evidence" class="evidence">证据：{{ evidence }}</p><StructuredTable :value="result.outputs" />
      </details>
    </section>
  </template>
</template>
<style scoped>
.job-section { padding: 24px; margin-bottom: 18px; } h2 { font-size: 18px; overflow-wrap: anywhere; } .refresh-button { width: auto; cursor: pointer; }
details { border-top: 1px solid #e4e8ef; padding: 14px 0; } summary { cursor: pointer; overflow-wrap: anywhere; }
.job-section { min-width: 0; }
.narrative { white-space: pre-wrap; } .evidence, .narrative { overflow-wrap: anywhere; }
.ai-section .failure-box { display: grid; gap: 10px; margin: 12px 0; padding: 13px 15px; border: 1px solid var(--line); border-radius: 6px; background: #f9fbfe; }
.ai-section .hint { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.muted { color: var(--muted); }
</style>
