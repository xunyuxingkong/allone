<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
type Job = { job_id: string; goal: string; state: string; revision?: number; error?: string }
const items = ref<Job[]>([])
const loading = ref(false)
const error = ref('')
async function refresh() {
  loading.value = true; error.value = ''
  try { items.value = (await api<{ items: Job[] }>('/api/jobs')).items }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '任务读取失败' }
  finally { loading.value = false }
}
onMounted(refresh)
</script>

<template>
  <div class="page-heading"><div><h1>测试任务</h1><p>由外部 Agent 驱动，查看测试进度与待处理事项。</p></div><button class="control refresh-button" :disabled="loading" @click="refresh">刷新</button></div>
  <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
  <section class="surface">
    <div class="table-scroll"><table class="data-table"><thead><tr><th>测试目标</th><th>状态</th><th>记录版本</th></tr></thead><tbody>
      <tr v-for="job in items" :key="job.job_id"><td><RouterLink class="link" :to="`/jobs/${job.job_id}`">{{ job.goal || job.job_id }}</RouterLink><div v-if="job.error">{{ job.error }}</div></td><td>{{ job.state }}</td><td>{{ job.revision ?? '—' }}</td></tr>
    </tbody></table></div>
    <p v-if="loading" class="empty-state">正在读取任务…</p><p v-else-if="!items.length" class="empty-state">尚无测试任务。向外部 Agent 描述测试目标即可创建。</p>
  </section>
</template>
<style scoped>.refresh-button { width: auto; cursor: pointer; }</style>
