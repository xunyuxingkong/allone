<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getScopeMatrix, type ScopeMatrixRow, type ScopeMatrixView } from '../api/generation'
import { getMission, type MissionView } from '../api/missions'
import StatCard from '../components/StatCard.vue'

const route = useRoute()
const missionId = computed(() => route.params.missionId as string | undefined)
const mission = ref<MissionView | null>(null)
const matrix = ref<ScopeMatrixView | null>(null)
const strategy = ref<'pairwise' | 'all_values'>('pairwise')
const loading = ref(false)
const error = ref('')

const STATUS_LABELS: Record<string, string> = { covered: '已覆盖', partial: '部分覆盖', missing: '未覆盖' }
const statusLabel = (status: string) => STATUS_LABELS[status] ?? status

// Group Core rows by dimension so the table reads as a test-space inventory.
const groups = computed(() => {
  const map = new Map<string, ScopeMatrixRow[]>()
  for (const row of matrix.value?.rows ?? []) {
    if (!map.has(row.dimension)) map.set(row.dimension, [])
    map.get(row.dimension)!.push(row)
  }
  return [...map.entries()].map(([dimension, rows]) => ({ dimension, rows: [...rows].sort((a, b) => a.value.localeCompare(b.value)) }))
})

async function refresh() {
  loading.value = true; error.value = ''
  try {
    if (missionId.value) mission.value = await getMission(missionId.value).catch(() => null)
    matrix.value = await getScopeMatrix(strategy.value)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '测试空间读取失败'
  } finally {
    loading.value = false
  }
}
watch(strategy, refresh)
watch(() => route.params.missionId, refresh)
onMounted(refresh)
</script>

<template>
  <div class="page-heading">
    <div>
      <RouterLink v-if="missionId" class="link" :to="`/tests/${missionId}`">← {{ mission?.mission.name ?? '测试目标' }}</RouterLink>
      <h1>测试空间</h1>
      <p>这个目标包含哪些场景、覆盖到什么程度、每个维度有多少用例。</p>
    </div>
    <div class="filter-field"><label for="strategy">覆盖策略</label>
      <select id="strategy" v-model="strategy" class="control"><option value="pairwise">Pairwise</option><option value="all_values">All Values</option></select>
    </div>
  </div>
  <div v-if="error" class="error-banner" role="alert">{{ error }}</div>

  <template v-if="matrix">
    <section class="surface scope-verdict">
      <div class="verdict-row">
        <span class="verdict-defined">{{ matrix.scope_verdict.defined_scope }}</span>
        <span class="verdict-module">{{ matrix.scope_verdict.module }}</span>
      </div>
      <p class="hint">“当前定义范围”指本模型声明的测试空间；它与 Query 全模块是否完整测试是两件事。</p>
    </section>

    <div class="scope-two">
      <section class="surface scope-block">
        <h2 class="surface-title">已测范围 <span class="title-count">{{ matrix.tested_scope.length }}</span></h2>
        <div class="scope-body"><ul class="chips"><li v-for="item in matrix.tested_scope" :key="`${item.dimension}-${item.value}`" class="chip ok">{{ item.label }}<em>{{ item.dimension }}</em></li><li v-if="!matrix.tested_scope.length" class="muted">—</li></ul></div>
      </section>
      <section class="surface scope-block">
        <h2 class="surface-title">未测范围 <span class="title-count">{{ matrix.untested_scope.length }}</span></h2>
        <div class="scope-body"><ul class="chips"><li v-for="item in matrix.untested_scope" :key="`${item.dimension}-${item.value}`" class="chip off">{{ item.label }}<em>{{ item.dimension }}</em></li><li v-if="!matrix.untested_scope.length" class="muted">—</li></ul></div>
      </section>
    </div>

    <section class="surface scope-summary">
      <div class="metric-row">
        <StatCard label="覆盖要求" :value="matrix.totals.requirements" />
        <StatCard label="已覆盖要求" :value="matrix.totals.covered" tone="pass" />
        <StatCard label="未覆盖要求" :value="matrix.totals.missing" tone="error" />
        <StatCard label="可执行用例" :value="matrix.totals.cases" />
        <StatCard label="SQL 执行" :value="matrix.totals.executions" />
      </div>
      <div class="count-note">
        <span><b>要求</b>：{{ matrix.count_semantics.requirements }}</span>
        <span><b>用例</b>：{{ matrix.count_semantics.cases }}</span>
        <span><b>执行</b>：{{ matrix.count_semantics.executions }}</span>
      </div>
    </section>

    <section v-for="group in groups" :key="group.dimension" class="surface scope-group">
      <h2 class="surface-title">{{ group.dimension }}</h2>
      <div class="table-scroll"><table class="data-table compact-table">
        <thead><tr><th>取值</th><th>要求</th><th>已覆盖</th><th>用例</th><th>SQL 执行</th><th>状态</th></tr></thead>
        <tbody><tr v-for="row in group.rows" :key="row.value">
          <td>{{ row.value }}</td>
          <td>{{ row.required }}</td>
          <td>{{ row.covered }}</td>
          <td>{{ row.cases }}</td>
          <td>{{ row.executions }}</td>
          <td><span class="status-tag" :class="`status-${row.status}`">{{ statusLabel(row.status) }}</span></td>
        </tr></tbody>
      </table></div>
    </section>
    <p class="hint">用例数不等于场景数：一个用例可覆盖多个要求，也可执行多步 SQL。模块层面仍为 {{ matrix.module_completion }}。</p>
  </template>
  <section v-else-if="loading" class="surface empty-state">正在读取测试空间…</section>
</template>

<style scoped>
.scope-verdict { padding: 16px 20px; margin-bottom: 16px; }
.verdict-row { display: flex; flex-wrap: wrap; gap: 10px 26px; align-items: baseline; }
.verdict-defined { color: #23354f; font-size: 16px; font-weight: 700; }
.verdict-module { color: var(--amber); font-size: 14px; font-weight: 700; }
.scope-verdict .hint { margin: 8px 0 0; }
.scope-two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.scope-block { overflow: hidden; }
.scope-body { padding: 16px 20px; }
.title-count { margin-left: 7px; color: #8592a4; font: 12px ui-monospace, Consolas, monospace; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
.chip { display: inline-flex; align-items: baseline; gap: 7px; padding: 5px 10px; border-radius: 5px; font-size: 13px; font-weight: 600; }
.chip em { color: var(--muted); font: 10px ui-monospace, Consolas, monospace; font-style: normal; }
.chip.ok { color: #17834b; background: #e7f5ed; }
.chip.off { color: #68778b; background: #eef1f5; }
.scope-summary { overflow: hidden; margin-bottom: 16px; }
.count-note { display: flex; flex-wrap: wrap; gap: 8px 26px; padding: 13px 20px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }
.count-note b { color: #23354f; }
.scope-group { overflow: hidden; margin-bottom: 16px; }
.status-covered { color: #17834b; background: #e7f5ed; }
.status-partial { color: #ae6a0a; background: #fff2db; }
.status-missing { color: #68778b; background: #eef1f5; }
.hint { color: var(--muted); font-size: 12px; }
.table-scroll { overflow-x: auto; }
.filter-field { display: grid; gap: 6px; min-width: 160px; }
.filter-field label { color: #718096; font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
@media (max-width: 900px) { .scope-two { grid-template-columns: 1fr; } }
</style>
