<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { listRuns, type Page } from '../api/runs'
import StatusTag from '../components/StatusTag.vue'
import { formatDate, formatDuration, shortId } from '../utils'
import type { RunSummary } from '../types'

const filters = reactive({ status: '', date_from: '', date_to: '' })
const page = ref<Page<RunSummary>>({ items: [], offset: 0, limit: 25 })
const offset = ref(0)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try { page.value = await listRuns({ ...filters, offset: offset.value, limit: 25 }) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '无法读取运行记录' }
  finally { loading.value = false }
}
function applyFilters() { offset.value = 0; void load() }
function nextPage() { if (page.value.next_offset != null) { offset.value = page.value.next_offset; void load() } }
function previousPage() { offset.value = Math.max(0, offset.value - page.value.limit); void load() }
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>运行记录</h1><p>按时间和状态查看 Query Run 历史。</p></div></div>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <section class="surface table-surface">
    <form class="filter-row" @submit.prevent="applyFilters">
      <div class="filter-field"><label for="date-from">开始日期</label><input id="date-from" v-model="filters.date_from" class="control" type="date" /></div>
      <div class="filter-field"><label for="date-to">结束日期</label><input id="date-to" v-model="filters.date_to" class="control" type="date" /></div>
      <div class="filter-field"><label for="run-status">运行状态</label><select id="run-status" v-model="filters.status" class="control"><option value="">全部状态</option><option>PASS</option><option>FAIL</option><option>ERROR</option><option>TIMEOUT</option></select></div>
      <button class="primary-button" type="submit">应用筛选</button>
    </form>
    <div class="table-scroll">
      <table class="data-table run-table"><thead><tr><th>Run ID</th><th>运行时间</th><th>数据库</th><th>Git Commit</th><th>总数</th><th>通过</th><th>失败</th><th>错误</th><th>超时</th><th>耗时</th><th>状态</th></tr></thead>
        <tbody><tr v-for="run in page.items" :key="run.run_id"><td><RouterLink class="link mono" :to="`/runs/${run.run_id}`">{{ shortId(run.run_id, 16) }}</RouterLink></td><td>{{ formatDate(run.started_at) }}</td><td>{{ run.database_alias }}</td><td class="mono">{{ shortId(run.git_commit, 10) }}</td><td>{{ run.case_count }}</td><td class="text-pass">{{ run.pass }}</td><td class="text-fail">{{ run.fail }}</td><td class="text-error">{{ run.error }}</td><td class="text-timeout">{{ run.timeout }}</td><td>{{ formatDuration(run.duration_ms) }}</td><td><StatusTag :status="run.status" /></td></tr></tbody>
      </table>
      <div v-if="!page.items.length" class="empty-state">{{ loading ? '读取中…' : '没有匹配的运行记录' }}</div>
    </div>
    <div class="pagination"><span>显示 {{ page.items.length ? offset + 1 : 0 }}–{{ offset + page.items.length }} 条记录</span><div class="page-buttons"><button type="button" :disabled="offset === 0 || loading" @click="previousPage">上一页</button><button type="button" :disabled="page.next_offset == null || loading" @click="nextPage">下一页</button></div></div>
  </section>
</template>

<style scoped>
.run-table { min-width: 980px; }.primary-button { height:36px;padding:0 15px;border:0;border-radius:5px;background:#1e4fae;color:#fff;font-size:12px;font-weight:600;cursor:pointer; }.primary-button:hover { background:#173f8d; }.page-buttons{display:flex;gap:7px}
</style>
