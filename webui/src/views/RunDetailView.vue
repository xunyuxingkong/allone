<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { getRun, listCases } from '../api/runs'
import { getScopeMatrix, type ScopeMatrixView } from '../api/generation'
import type { QueryCaseReport, QueryRunReport } from '../types'
import StatusTag from '../components/StatusTag.vue'
import StatCard from '../components/StatCard.vue'
import CaseTable from '../components/CaseTable.vue'
import { formatDate, formatDuration, shortId } from '../utils'

const props = defineProps<{ runId: string }>()
const run = ref<QueryRunReport | null>(null)
const scope = ref<ScopeMatrixView | null>(null)
const cases = ref<QueryCaseReport[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const filters = reactive({ case_id: '', feature: '', status: '', failure_type: '' })
const sortDir = ref<'asc' | 'desc' | null>(null)
const featureOptions = computed(() =>
  [...new Set((run.value?.cases ?? []).map((item) => item.feature).filter((value): value is string => Boolean(value)))].sort(),
)
const failureOptions = computed(() =>
  [...new Set((run.value?.cases ?? []).map((item) => item.failure_type).filter((value): value is string => Boolean(value)))].sort(),
)

function count(status: string) {
  return run.value?.cases.filter((item) => item.status === status).length ?? 0
}

async function loadRunMeta() {
  run.value = await getRun(props.runId)
}

async function loadCases() {
  const result = await listCases(props.runId, {
    case_id: filters.case_id || undefined,
    feature: filters.feature || undefined,
    status: filters.status || undefined,
    failure_type: filters.failure_type || undefined,
    sort_by: sortDir.value ? 'duration_ms' : undefined,
    sort_dir: sortDir.value ?? undefined,
    limit: 500,
  })
  cases.value = result.items
  total.value = result.total ?? result.items.length
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await loadRunMeta()
    await loadCases()
    // Scope is a Core-derived property of the active set, shown alongside the run result.
    scope.value = await getScopeMatrix('pairwise').catch(() => null)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法读取运行详情'
  } finally {
    loading.value = false
  }
}

async function applyFilters() {
  loading.value = true
  error.value = ''
  try {
    await loadCases()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法筛选 Case'
  } finally {
    loading.value = false
  }
}

function toggleDurationSort() {
  sortDir.value = sortDir.value === 'desc' ? 'asc' : sortDir.value === 'asc' ? null : 'desc'
  void applyFilters()
}

onMounted(load)
watch(() => props.runId, load)
</script>

<template>
  <div class="back-row"><RouterLink to="/runs" class="link">← 返回运行记录</RouterLink></div>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <template v-if="run">
    <div class="page-heading run-heading">
      <div>
        <h1 class="mono">{{ run.run_id }}</h1>
        <p>开始于 {{ formatDate(run.started_at) }} · {{ formatDuration(new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) }}</p>
      </div>
      <StatusTag :status="run.status" />
    </div>
    <section class="surface run-metadata">
      <div class="meta-grid">
        <div class="meta-item"><span>数据库</span><b>{{ run.target.database_alias }}</b></div>
        <div class="meta-item"><span>Git Commit</span><b>{{ shortId(run.git_commit, 16) }}</b></div>
        <div class="meta-item"><span>Runtime Profile ID</span><b>{{ shortId(run.target.sql_runtime_profile_id) }}</b></div>
        <div class="meta-item"><span>Contract Set ID</span><b>{{ shortId(run.target.contract_set_id) }}</b></div>
      </div>
      <div class="metric-row">
        <StatCard label="用例总数" :value="run.cases.length" />
        <StatCard label="通过" :value="count('PASS')" tone="pass" />
        <StatCard label="失败" :value="count('FAIL')" tone="fail" />
        <StatCard label="错误" :value="count('ERROR')" tone="error" />
        <StatCard label="超时" :value="count('TIMEOUT')" tone="timeout" />
      </div>
    </section>
    <section v-if="scope" class="surface scope-surface">
      <h2 class="surface-title">本次测试范围</h2>
      <div class="scope-verdict">
        <span class="verdict-defined">{{ scope.scope_verdict.defined_scope }}</span>
        <span class="verdict-module">{{ scope.scope_verdict.module }}</span>
      </div>
      <div class="scope-columns">
        <div>
          <h3>已测范围（{{ scope.tested_scope.length }}）</h3>
          <ul class="scope-list"><li v-for="item in scope.tested_scope" :key="`t-${item.dimension}-${item.value}`" class="ok">✓ {{ item.label }}</li><li v-if="!scope.tested_scope.length" class="muted">—</li></ul>
        </div>
        <div>
          <h3>未测范围（{{ scope.untested_scope.length }}）</h3>
          <ul class="scope-list"><li v-for="item in scope.untested_scope" :key="`u-${item.dimension}-${item.value}`" class="off">✗ {{ item.label }}</li><li v-if="!scope.untested_scope.length" class="muted">—</li></ul>
        </div>
      </div>
      <p class="scope-note">一次运行通过只代表当前定义范围内通过；未测范围与 Query 全模块完整性另行判定。详见<RouterLink class="link" to="/coverage"> 覆盖情况 </RouterLink>。</p>
    </section>
    <section class="surface table-surface cases-surface">
      <h2 class="surface-title">Case 结果 <span class="title-count">{{ total }} 条</span></h2>
      <form class="filter-row" @submit.prevent="applyFilters">
        <div class="filter-field wide">
          <label for="case-search">Case ID</label>
          <input id="case-search" v-model="filters.case_id" class="control" type="search" placeholder="搜索 Case ID" />
        </div>
        <div class="filter-field">
          <label for="feature-filter">Feature</label>
          <select id="feature-filter" v-model="filters.feature" class="control">
            <option value="">全部 Feature</option>
            <option v-for="feature in featureOptions" :key="feature">{{ feature }}</option>
          </select>
        </div>
        <div class="filter-field">
          <label for="status-filter">状态</label>
          <select id="status-filter" v-model="filters.status" class="control">
            <option value="">全部状态</option>
            <option>PASS</option>
            <option>FAIL</option>
            <option>ERROR</option>
            <option>TIMEOUT</option>
          </select>
        </div>
        <div class="filter-field">
          <label for="failure-filter">Failure Type</label>
          <select id="failure-filter" v-model="filters.failure_type" class="control">
            <option value="">全部类型</option>
            <option v-for="failure in failureOptions" :key="failure">{{ failure }}</option>
          </select>
        </div>
        <button class="primary-button" type="submit">应用筛选</button>
      </form>
      <CaseTable
        :run-id="run.run_id"
        :cases="cases"
        :loading="loading"
        sortable
        :sort-dir="sortDir"
        @sort-duration="toggleDurationSort"
      />
    </section>
  </template>
  <div v-else-if="!error" class="surface empty-state">{{ loading ? '读取运行详情…' : '运行记录不存在' }}</div>
</template>

<style scoped>
.back-row { margin: 0 0 18px; font-size: 12px; }
.run-heading { align-items: center; margin-bottom: 16px; }
.run-heading h1 { font-size: 22px; overflow-wrap: anywhere; }
.run-metadata { overflow: hidden; }
.cases-surface { margin-top: 16px; }
.scope-surface { margin-top: 16px; padding-bottom: 4px; }
.scope-verdict { display: flex; flex-wrap: wrap; gap: 10px 26px; align-items: baseline; padding: 15px 20px 4px; }
.verdict-defined { color: #23354f; font-size: 15px; font-weight: 700; }
.verdict-module { color: var(--amber); font-size: 13px; font-weight: 700; }
.scope-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding: 12px 20px; }
.scope-columns h3 { margin: 0 0 10px; font-size: 13px; color: #53647b; }
.scope-list { display: flex; flex-wrap: wrap; gap: 7px; margin: 0; padding: 0; list-style: none; }
.scope-list li { padding: 4px 9px; border-radius: 5px; font-size: 12px; font-weight: 600; }
.scope-list li.ok { color: #17834b; background: #e7f5ed; }
.scope-list li.off { color: #68778b; background: #eef1f5; }
.scope-note { margin: 0; padding: 6px 20px 16px; color: var(--muted); font-size: 12px; }
.title-count { margin-left: 7px; color: #8592a4; font: 11px ui-monospace, Consolas, monospace; }
.primary-button {
  height: 36px;
  padding: 0 15px;
  border: 0;
  border-radius: 5px;
  background: #1e4fae;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.primary-button:hover { background: #173f8d; }
@media (max-width: 900px) { .scope-columns { grid-template-columns: 1fr; } }
</style>
