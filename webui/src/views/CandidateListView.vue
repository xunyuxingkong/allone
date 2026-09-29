<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getCandidates, trialEvidenceLabel, type CandidateSummary } from '../api/generation'

const items = ref<CandidateSummary[]>([])
const status = ref('')
const search = ref('')
const error = ref('')
const loading = ref(false)

async function refresh() {
  loading.value = true
  error.value = ''
  try { items.value = (await getCandidates()).items }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '候选读取失败' }
  finally { loading.value = false }
}
onMounted(refresh)
const filtered = computed(() => items.value.filter((item) =>
  (!status.value || item.status === status.value) &&
  (!search.value || item.case_id.toLowerCase().includes(search.value.toLowerCase()))
))
const assignmentText = (assignment: Record<string, string>) => Object.entries(assignment).map(([key, value]) => `${key}=${value}`).join(' · ')
</script>

<template>
  <div class="page-heading"><div><h1>候选用例</h1><p>查看 JOIN 候选的维度、试运行与评审状态。</p></div><span class="heading-meta">{{ items.length }} 条候选</span></div>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <section class="surface">
    <div class="filter-row">
      <div class="filter-field wide"><label for="candidate-search">Case ID</label><input id="candidate-search" v-model="search" class="control" placeholder="搜索候选 ID" /></div>
      <div class="filter-field"><label for="candidate-status">状态</label><select id="candidate-status" v-model="status" class="control"><option value="">全部</option><option value="generated">generated</option><option value="draft">draft</option><option value="review">review</option></select></div>
      <button class="control refresh-button" type="button" @click="refresh">刷新</button>
    </div>
    <div class="table-scroll"><table class="data-table"><thead><tr><th>Case ID</th><th>维度组合</th><th>状态</th><th>双跑证据</th><th>人工评审</th></tr></thead><tbody>
      <tr v-for="item in filtered" :key="item.case_id"><td><RouterLink class="link mono" :to="`/candidates/${item.case_id}`">{{ item.case_id }}</RouterLink></td><td>{{ assignmentText(item.assignment) }}</td><td>{{ item.status }}</td><td>{{ trialEvidenceLabel(item.trial_evidence_status) }}</td><td>{{ item.review_recorded ? '已记录' : '待评审' }}</td></tr>
    </tbody></table></div>
    <div v-if="loading" class="empty-state">正在读取候选…</div><div v-else-if="!filtered.length" class="empty-state">当前筛选下没有候选</div>
  </section>
</template>

<style scoped>
.refresh-button { width: auto; min-width: 70px; cursor: pointer; }
</style>
