<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { getCoverage, type CoverageView } from '../api/generation'
import StatCard from '../components/StatCard.vue'

const strategy = ref<'pairwise' | 'all_values'>('pairwise')
const selectedDimension = ref('')
const selectedGroup = ref<string[]>([])
const coverage = ref<CoverageView | null>(null)
const loading = ref(false)
const error = ref('')
let refreshVersion = 0

async function refresh() {
  const version = ++refreshVersion
  const requestedStrategy = strategy.value
  loading.value = true
  error.value = ''
  coverage.value = null
  selectedDimension.value = ''
  selectedGroup.value = []
  try {
    const result = await getCoverage(requestedStrategy)
    if (version === refreshVersion) coverage.value = result
  } catch (cause) {
    if (version === refreshVersion) error.value = cause instanceof Error ? cause.message : '覆盖数据读取失败'
  } finally {
    if (version === refreshVersion) loading.value = false
  }
}

onMounted(refresh)
watch(strategy, refresh)
const dimensions = computed(() => [...new Set((coverage.value?.missing_requirements ?? []).flatMap((item) => Object.keys(item.selections)))].sort())
const missing = computed(() => (coverage.value?.missing_requirements ?? []).filter((item) =>
  (!selectedDimension.value || selectedDimension.value in item.selections) &&
  selectedGroup.value.every((name) => name in item.selections)
))
const selectionText = (item: Record<string, string>) => Object.entries(item).map(([key, value]) => `${key}=${value}`).join(' · ')
</script>

<template>
  <div class="page-heading">
    <div><h1>覆盖情况</h1><p>查看 JOIN 模型的正式覆盖与待评审候选可补齐的组合。</p></div>
    <span class="heading-meta">Model {{ coverage?.model_version ?? '—' }}</span>
  </div>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <section class="surface coverage-overview">
    <div class="filter-row">
      <div class="filter-field"><label for="strategy">覆盖策略</label><select id="strategy" v-model="strategy" class="control"><option value="pairwise">Pairwise</option><option value="all_values">All Values</option></select></div>
      <div class="filter-field"><label for="dimension">缺口维度</label><select id="dimension" v-model="selectedDimension" class="control"><option value="">全部</option><option v-for="name in dimensions" :key="name" :value="name">{{ name }}</option></select></div>
      <RouterLink class="link coverage-candidate-link" to="/candidates">查看候选 →</RouterLink>
    </div>
    <div v-if="coverage" class="coverage-metrics">
      <StatCard label="要求组合" :value="coverage.required" />
      <StatCard label="正式覆盖" :value="coverage.active_covered" tone="pass" />
      <StatCard label="正式缺口" :value="coverage.active_missing" tone="error" />
      <StatCard label="待评审候选" :value="coverage.review_candidate_count" />
      <StatCard label="候选晋级后预计缺口" :value="coverage.provisional_missing" :tone="coverage.provisional_missing ? 'error' : 'pass'" />
    </div>
    <div v-if="coverage" class="coverage-note">候选覆盖仅为预计值；人工评审、晋级和回归完成前，不计入正式覆盖。</div>
    <div v-if="loading" class="empty-state">正在计算覆盖缺口…</div>
  </section>
  <section v-if="coverage" class="surface coverage-matrix">
    <h2 class="surface-title">维度覆盖矩阵</h2>
    <div class="table-scroll"><table class="data-table"><thead><tr><th>维度组合</th><th>要求</th><th>正式覆盖</th><th>候选晋级后预计</th><th>正式缺口</th></tr></thead><tbody>
      <tr v-for="row in coverage.matrix" :key="row.dimensions.join(':')">
        <td><a href="#coverage-gaps" class="link mono" @click="selectedGroup = row.dimensions">{{ row.dimensions.join(' × ') }}</a></td><td>{{ row.required }}</td><td>{{ row.active_covered }}</td><td>{{ row.provisional_covered }}</td><td>{{ row.required - row.active_covered }}</td>
      </tr>
    </tbody></table></div>
  </section>
  <section v-if="coverage" class="surface model-detail">
    <details><summary>JOIN 模型详情 · v{{ coverage.model_version }}</summary>
      <div class="table-scroll"><table class="data-table"><thead><tr><th>维度</th><th>可选值</th></tr></thead><tbody>
        <tr v-for="(values, name) in coverage.dimensions" :key="name"><td class="mono">{{ name }}</td><td>{{ values.join(' · ') }}</td></tr>
      </tbody></table></div>
      <h3>约束</h3><pre class="code-block">{{ JSON.stringify(coverage.constraints, null, 2) }}</pre>
    </details>
  </section>
  <section id="coverage-gaps" class="surface">
    <h2 class="surface-title">尚未正式覆盖的组合 <span class="muted">({{ missing.length }})</span><button v-if="selectedGroup.length" type="button" class="link clear-group" @click="selectedGroup = []">清除 {{ selectedGroup.join(' × ') }} 筛选</button></h2>
    <div class="table-scroll"><table class="data-table"><thead><tr><th>组合要求</th><th>Requirement ID</th><th>覆盖该组合的待评审候选</th></tr></thead><tbody>
      <tr v-for="item in missing" :key="item.requirement_id"><td>{{ selectionText(item.selections) }}</td><td class="mono">{{ item.requirement_id }}</td><td><template v-if="item.candidate_case_ids.length"><RouterLink v-for="caseId in item.candidate_case_ids" :key="caseId" class="link candidate-link mono" :to="`/candidates/${caseId}`">{{ caseId }}</RouterLink></template><span v-else class="muted">暂无</span></td></tr>
    </tbody></table></div>
    <div v-if="!loading && !missing.length" class="empty-state">当前筛选下没有覆盖缺口</div>
  </section>
</template>

<style scoped>
.coverage-overview { margin-bottom: 16px; }
.coverage-matrix, .model-detail { margin-bottom: 16px; }
.model-detail summary { cursor: pointer; padding: 17px 20px; font-weight: 700; }
.model-detail h3 { margin: 14px 20px; font-size: 13px; }
.coverage-metrics { display: grid; grid-template-columns: repeat(5, 1fr); padding: 15px 2px; }
.coverage-note { border-top: 1px solid var(--line); padding: 12px 20px; color: var(--muted); font-size: 12px; }
.coverage-candidate-link { margin-left: auto; padding-bottom: 9px; }
.candidate-link { display: block; margin: 2px 0; }
.clear-group { margin-left: 12px; border: 0; background: none; cursor: pointer; font-size: 12px; }
@media (max-width: 850px) { .coverage-metrics { grid-template-columns: repeat(2, 1fr); gap: 14px 0; } }
@media (max-width: 600px) { .coverage-candidate-link { margin-left: 0; } .coverage-metrics { grid-template-columns: repeat(2, 1fr); } }
</style>
