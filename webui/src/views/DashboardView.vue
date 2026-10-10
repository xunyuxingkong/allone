<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useRunsStore } from '../stores/runs'
import { getCoverage, type CoverageView } from '../api/generation'
import { listMissions, type MissionSummary } from '../api/missions'
import StatCard from '../components/StatCard.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatDate, formatDuration, shortId } from '../utils'

const store = useRunsStore()
const missions = ref<MissionSummary[]>([])
const coverage = ref<CoverageView | null>(null)
const error = ref('')
const loading = ref(false)

const ACTIVE = ['READY', 'RUNNING', 'WAITING_APPROVAL', 'BLOCKED']
const current = computed(() => missions.value.find((item) => ACTIVE.includes(item.state)) ?? null)
const latest = computed(() => store.recent[0] ?? null)
const coverageRows = computed(() => coverage.value?.matrix ?? [])
// Preserve the Core wording: the defined scope may be complete while the module is not.
const scopeCompletion = computed(() => {
  const missing = coverage.value?.active_missing ?? 0
  return missing === 0 ? '当前定义范围：完成' : `当前定义范围：还缺 ${missing} 项`
})

async function refresh() {
  loading.value = true; error.value = ''
  try {
    const [missionResponse, coverageResponse] = await Promise.all([
      listMissions().catch(() => ({ items: [] as MissionSummary[] })),
      getCoverage('pairwise').catch(() => null),
    ])
    missions.value = missionResponse.items
    coverage.value = coverageResponse
    await store.refreshRecent()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '仪表盘读取失败'
  } finally {
    loading.value = false
  }
}
onMounted(refresh)
</script>

<template>
  <div class="page-heading">
    <div><h1>仪表盘</h1><p>现在在测什么、覆盖到什么程度、最近结果怎么样。</p></div>
    <span class="heading-meta">{{ current ? current.name : '尚无测试目标' }}</span>
  </div>
  <div v-if="error" class="error-banner" role="alert">{{ error }}</div>

  <section class="surface mission-top">
    <div class="mission-top-head">
      <div>
        <span class="eyebrow-label">当前测试目标</span>
        <h2 v-if="current"><RouterLink class="link mission-name" :to="`/tests/${current.mission_id}`">{{ current.name }}</RouterLink></h2>
        <h2 v-else class="muted">尚未创建测试目标</h2>
      </div>
      <RouterLink class="control start-action" to="/tests/new">开始 AI 测试</RouterLink>
    </div>
    <div v-if="current" class="meta-grid">
      <div class="meta-item"><span>范围</span><b>{{ current.features.join(' / ') || '—' }}</b></div>
      <div class="meta-item"><span>模式</span><b>{{ current.strategy }}</b></div>
      <div class="meta-item"><span>状态</span><b>{{ current.state }}</b></div>
      <div class="meta-item"><span>关联任务</span><b>{{ current.job_id ? shortId(current.job_id) : '未启动' }}</b></div>
    </div>
    <p v-else class="mission-empty">先说明为什么测、测什么、不测什么，再启动 AI 测试。<RouterLink class="link" to="/tests/new">创建测试目标 →</RouterLink></p>
  </section>

  <div class="dashboard-top">
    <section class="surface coverage-panel">
      <div class="section-heading"><h2 class="surface-title">Query 覆盖</h2><RouterLink class="link" to="/coverage">查看覆盖详情 →</RouterLink></div>
      <div v-if="coverage" class="metric-row">
        <StatCard label="要求组合" :value="coverage.required" />
        <StatCard label="正式覆盖" :value="coverage.active_covered" tone="pass" />
        <StatCard label="正式缺口" :value="coverage.active_missing" tone="error" />
        <StatCard label="待评审候选" :value="coverage.review_candidate_count" />
        <StatCard label="候选晋级后预计缺口" :value="coverage.provisional_missing" :tone="coverage.provisional_missing ? 'error' : 'pass'" />
      </div>
      <div class="scope-note"><span>{{ scopeCompletion }}</span><span class="muted">模块层面：未完整（MODULE_FULL_INCOMPLETE）</span></div>
      <div class="table-scroll" v-if="coverageRows.length">
        <table class="data-table compact-table">
          <thead><tr><th>覆盖维度</th><th>要求</th><th>正式覆盖</th><th>候选晋级后</th></tr></thead>
          <tbody><tr v-for="row in coverageRows" :key="row.dimensions.join('·')">
            <td>{{ row.dimensions.join(' · ') || '—' }}</td>
            <td>{{ row.required }}</td>
            <td>{{ row.active_covered }}</td>
            <td>{{ row.provisional_covered }}</td>
          </tr></tbody>
        </table>
      </div>
      <p v-else-if="!loading" class="empty-state">暂无覆盖维度数据。</p>
    </section>

    <section class="surface latest-run">
      <h2 class="surface-title">最近测试</h2>
      <template v-if="latest">
        <div class="latest-head">
          <div><span class="eyebrow-label">最近一次运行</span>
            <RouterLink class="run-title mono" :to="`/runs/${latest.run_id}`">{{ shortId(latest.run_id, 16) }} <span class="arrow">↗</span></RouterLink></div>
          <StatusTag :status="latest.status" />
        </div>
        <div class="run-summary">
          <span><b>{{ latest.case_count }}</b> Cases</span>
          <span class="text-pass"><b>{{ latest.pass }}</b> PASS</span>
          <span :class="latest.fail ? 'text-fail' : 'muted'"><b>{{ latest.fail }}</b> FAIL</span>
          <span class="muted"><b>{{ latest.error + latest.timeout }}</b> 异常</span>
        </div>
        <div class="run-foot">
          <span>通过率 <b>{{ latest.pass_rate.toFixed(1) }}%</b></span>
          <span>耗时 <b>{{ formatDuration(latest.duration_ms) }}</b></span>
          <RouterLink class="link" :to="`/runs/${latest.run_id}`">运行详情 →</RouterLink>
        </div>
      </template>
      <p v-else class="empty-state">{{ store.loading ? '正在读取运行历史…' : '暂无运行记录。' }}</p>
    </section>
  </div>

  <section class="surface dashboard-table">
    <div class="section-heading"><h2 class="surface-title">最近运行记录</h2><RouterLink class="link" to="/runs">查看全部 →</RouterLink></div>
    <div class="table-scroll">
      <table class="data-table compact-table">
        <thead><tr><th>Run ID</th><th>开始时间</th><th>数据库</th><th>状态</th><th>通过率</th><th>耗时</th></tr></thead>
        <tbody><tr v-for="run in store.recent.slice(0, 5)" :key="run.run_id">
          <td><RouterLink class="link mono" :to="`/runs/${run.run_id}`">{{ shortId(run.run_id, 16) }}</RouterLink></td>
          <td>{{ formatDate(run.started_at) }}</td>
          <td>{{ run.database_alias }}</td>
          <td><StatusTag :status="run.status" /></td>
          <td>{{ run.pass_rate.toFixed(1) }}%</td>
          <td>{{ formatDuration(run.duration_ms) }}</td>
        </tr></tbody>
      </table>
      <div v-if="!store.recent.length" class="empty-state">暂无运行记录</div>
    </div>
  </section>
</template>

<style scoped>
.mission-top { overflow: hidden; margin-bottom: 16px; }
.mission-top-head { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 20px 20px 4px; }
.mission-name { font-size: 20px; }
.eyebrow-label { display: block; margin-bottom: 8px; color: #74839a; font-size: 11px; }
.start-action { width: auto; min-width: 150px; height: 40px; display: inline-flex; align-items: center; justify-content: center; border-color: #17499d; background: #1e4fae; color: #fff; font-weight: 700; white-space: nowrap; }
.mission-empty { margin: 0; padding: 4px 20px 20px; color: var(--muted); font-size: 13px; }
.dashboard-top { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(280px, .9fr); gap: 16px; }
.coverage-panel, .latest-run { overflow: hidden; }
.section-heading { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--line); padding-right: 18px; }
.section-heading .surface-title { border: 0; }
.scope-note { display: flex; justify-content: space-between; gap: 12px; padding: 12px 20px; border-top: 1px solid var(--line); font-size: 12px; font-weight: 600; color: #23354f; }
.latest-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 20px 0; }
.run-title { color: #1e4fae; font-size: 15px; font-weight: 600; }
.arrow { margin-left: 4px; color: #8190a3; }
.run-summary { display: flex; flex-wrap: wrap; gap: 10px 22px; padding: 16px 20px; font-size: 13px; }
.run-summary b { font-size: 18px; font-weight: 700; }
.run-foot { display: flex; align-items: center; gap: 20px; border-top: 1px solid var(--line); padding: 12px 20px; color: #718096; font-size: 11px; }
.run-foot b { color: #31445e; font-weight: 700; }
.run-foot .link { margin-left: auto; }
.dashboard-table { margin-top: 16px; overflow: hidden; }
.table-scroll { overflow-x: auto; }
@media (max-width: 1050px) { .dashboard-top { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 600px) { .mission-top-head { flex-direction: column; align-items: stretch; } .run-foot { flex-wrap: wrap; gap: 10px 16px; } .run-foot .link { width: 100%; margin-left: 0; } }
</style>
