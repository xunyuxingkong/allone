<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { RouterLink } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { GraphicComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { useRunsStore } from '../stores/runs'
import StatusTag from '../components/StatusTag.vue'
import StatCard from '../components/StatCard.vue'
import { formatDate, formatDuration, shortId } from '../utils'

use([CanvasRenderer, PieChart, GraphicComponent, LegendComponent, TooltipComponent])

const store = useRunsStore()
onMounted(store.refreshRecent)
watch(() => store.recent[0]?.run_id, (runId) => { if (runId) store.loadRun(runId) })

const latest = computed(() => store.recent[0] ?? null)
const slowest = computed(() => [...(store.selected?.cases ?? [])].sort((a, b) => b.duration_ms - a.duration_ms).slice(0, 5))
const statusCounts = computed(() => [
  { name: '通过', value: latest.value?.pass ?? 0 },
  { name: '失败', value: latest.value?.fail ?? 0 },
  { name: '错误', value: latest.value?.error ?? 0 },
  { name: '超时', value: latest.value?.timeout ?? 0 },
].filter((item) => item.value > 0))
const chartOption = computed(() => ({
  color: ['#28a566', '#e04e4e', '#df9821', '#3472d4'],
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'middle',
    itemWidth: 9,
    itemHeight: 9,
    itemGap: 15,
    textStyle: { color: '#52647d', fontSize: 12 },
    formatter: (name: string) => {
      const item = statusCounts.value.find((entry) => entry.name === name)
      const total = latest.value?.case_count ?? 0
      return `${name}  ${item?.value ?? 0} (${total ? (((item?.value ?? 0) / total) * 100).toFixed(1) : '0.0'}%)`
    },
  },
  graphic: [{
    type: 'text',
    left: '27%',
    top: '43%',
    style: {
      text: `${latest.value?.case_count ?? 0}\n总数`,
      textAlign: 'center',
      fill: '#253b59',
      fontSize: 15,
      fontWeight: 700,
      lineHeight: 23,
    },
  }],
  series: [{
    name: '用例状态',
    type: 'pie',
    radius: ['54%', '76%'],
    center: ['32%', '53%'],
    avoidLabelOverlap: true,
    label: { show: false },
    emphasis: { scale: true, scaleSize: 5 },
    itemStyle: { borderColor: '#fff', borderWidth: 2 },
    data: statusCounts.value,
  }],
}))
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>仪表盘</h1>
      <p>查看最近 Query Run 与只读验收结果。</p>
    </div>
    <span class="heading-meta">{{ latest ? formatDate(latest.started_at) : '等待运行记录' }}</span>
  </div>
  <div v-if="store.error" class="error-banner">{{ store.error }}</div>

  <div v-if="latest" class="dashboard-top">
    <section class="surface latest-run">
      <div class="latest-head">
        <div>
          <span class="eyebrow-label">最近一次查询运行</span>
          <RouterLink class="run-title mono" :to="`/runs/${latest.run_id}`">{{ shortId(latest.run_id, 16) }} <span class="arrow">↗</span></RouterLink>
        </div>
        <StatusTag :status="latest.status" />
      </div>
      <div class="meta-grid">
        <div class="meta-item"><span>数据库</span><b>{{ latest.database_alias }}</b></div>
        <div class="meta-item"><span>Git Commit</span><b>{{ shortId(latest.git_commit, 12) }}</b></div>
        <div class="meta-item"><span>Runtime Profile</span><b>{{ shortId(store.selected?.target.sql_runtime_profile_id) }}</b></div>
        <div class="meta-item"><span>Contract Set</span><b>{{ shortId(store.selected?.target.contract_set_id) }}</b></div>
      </div>
      <div class="metric-row">
        <StatCard label="用例总数" :value="latest.case_count" />
        <StatCard label="通过" :value="latest.pass" tone="pass" />
        <StatCard label="失败" :value="latest.fail" tone="fail" />
        <StatCard label="错误" :value="latest.error" tone="error" />
        <StatCard label="超时" :value="latest.timeout" tone="timeout" />
      </div>
      <div class="run-foot">
        <span>通过率 <b>{{ latest.pass_rate.toFixed(1) }}%</b></span>
        <span>运行耗时 <b>{{ formatDuration(latest.duration_ms) }}</b></span>
        <RouterLink class="link" :to="`/runs/${latest.run_id}`">查看运行详情 →</RouterLink>
      </div>
    </section>
    <section class="surface status-distribution">
      <h2 class="surface-title">本次运行状态分布</h2>
      <div v-if="latest.case_count" class="chart-wrap"><VChart :option="chartOption" autoresize /></div>
      <div v-else class="empty-state">本次运行没有用例结果</div>
    </section>
  </div>
  <section v-else class="surface empty-state">
    {{ store.loading ? '正在读取运行历史…' : '暂无 Query Run。运行 xgtest query run 后，结果会显示在这里。' }}
  </section>

  <section class="surface dashboard-table">
    <div class="section-heading"><h2 class="surface-title">最近运行记录</h2><RouterLink class="link" to="/runs">查看全部 →</RouterLink></div>
    <div class="table-scroll">
      <table class="data-table compact-table">
        <thead><tr><th>Run ID</th><th>开始时间</th><th>数据库</th><th>Git Commit</th><th>状态</th><th>通过率</th><th>运行耗时</th></tr></thead>
        <tbody>
          <tr v-for="run in store.recent.slice(0, 5)" :key="run.run_id">
            <td><RouterLink class="link mono" :to="`/runs/${run.run_id}`">{{ shortId(run.run_id, 16) }}</RouterLink></td>
            <td>{{ formatDate(run.started_at) }}</td>
            <td>{{ run.database_alias }}</td>
            <td class="mono">{{ shortId(run.git_commit, 10) }}</td>
            <td><StatusTag :status="run.status" /></td>
            <td>{{ run.pass_rate.toFixed(1) }}%</td>
            <td>{{ formatDuration(run.duration_ms) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!store.recent.length" class="empty-state">暂无运行记录</div>
    </div>
  </section>

  <section class="surface dashboard-table slowest-section">
    <h2 class="surface-title">耗时最长的用例（Top 5）</h2>
    <div class="table-scroll">
      <table class="data-table compact-table">
        <thead><tr><th>排名</th><th>Case ID</th><th>Feature</th><th>数据库</th><th>状态</th><th>耗时</th></tr></thead>
        <tbody>
          <tr v-for="(item, index) in slowest" :key="item.case_id">
            <td>{{ String(index + 1).padStart(2, '0') }}</td>
            <td><RouterLink class="link mono" :to="`/runs/${latest?.run_id}/cases/${item.case_id}`">{{ item.case_id }}</RouterLink></td>
            <td>{{ item.feature ?? '—' }}</td>
            <td>{{ latest?.database_alias ?? '—' }}</td>
            <td><StatusTag :status="item.status" /></td>
            <td>{{ formatDuration(item.duration_ms) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!slowest.length" class="empty-state">最近一次运行没有用例耗时数据</div>
    </div>
  </section>
</template>

<style scoped>
.latest-run { overflow: hidden; }
.dashboard-top { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(280px, .8fr); gap: 16px; }
.status-distribution { min-width: 0; }
.status-distribution .surface-title { padding-bottom: 12px; }
.dashboard-table { margin-top: 16px; overflow: hidden; }
.section-heading { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--line); padding-right: 18px; }
.section-heading .surface-title { border: 0; }
.latest-head { display: flex; align-items: center; justify-content: space-between; padding: 19px 20px 0; }
.eyebrow-label { display: block; margin-bottom: 8px; color: #74839a; font-size: 11px; }
.run-title { color: #1e4fae; font-size: 16px; font-weight: 600; }
.arrow { margin-left: 4px; color: #8190a3; }
.run-foot { display: flex; align-items: center; gap: 24px; border-top: 1px solid var(--line); padding: 12px 20px; color: #718096; font-size: 11px; }
.run-foot b { color: #31445e; font-weight: 700; }
.run-foot .link { margin-left: auto; }
.table-scroll { overflow-x: auto; }
@media (max-width: 1050px) {
  .dashboard-top { grid-template-columns: minmax(0, 1fr); }
  .status-distribution .chart-wrap { height: 220px; }
}
@media (max-width: 600px) {
  .status-distribution .chart-wrap { height: 200px; }
  .run-foot { flex-wrap: wrap; gap: 10px 16px; }
  .run-foot .link { width: 100%; margin-left: 0; }
  .latest-head { padding-left: 15px; padding-right: 15px; }
}
</style>
