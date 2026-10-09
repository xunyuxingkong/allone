<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getMission, listMissions, type MissionSummary, type MissionView } from '../api/missions'
import { shortId } from '../utils'

const route = useRoute()
const missionId = computed(() => route.params.missionId as string | undefined)
const missions = ref<MissionSummary[]>([])
const detail = ref<MissionView | null>(null)
const loading = ref(false)
const error = ref('')

async function refresh() {
  const current = missionId.value
  loading.value = true; error.value = ''
  detail.value = null
  try {
    if (current) detail.value = await getMission(current)
    else missions.value = (await listMissions()).items
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '测试任务读取失败' }
  finally { loading.value = false }
}
// List and detail share one component, so navigate reuses the instance; watch the param.
watch(() => route.params.missionId, refresh)
onMounted(refresh)
</script>

<template>
  <div class="page-heading">
    <div><RouterLink v-if="missionId" class="link" to="/tests">← 测试目标</RouterLink><h1>{{ detail ? detail.mission.name : '测试目标' }}</h1>
      <p>测试目标 → 测试任务 → 运行记录。测试目标说明为什么测、测什么、不测什么。</p></div>
    <RouterLink class="link create-link" to="/tests/new">＋ 创建测试任务</RouterLink>
  </div>
  <div v-if="error" class="error-banner" role="alert">{{ error }}</div>

  <template v-if="detail">
    <section class="surface mission-block">
      <h2 class="surface-title">测试目的</h2>
      <div class="mission-body"><p class="narrative">{{ detail.mission.purpose }}</p></div>
    </section>
    <div class="mission-two">
      <section class="surface mission-block">
        <h2 class="surface-title">测试范围（测什么）</h2>
        <div class="mission-body"><ul class="chips"><li v-for="item in detail.tested_scope" :key="item" class="chip ok">✓ {{ item }}</li><li v-if="!detail.tested_scope.length" class="muted">—</li></ul></div>
      </section>
      <section class="surface mission-block">
        <h2 class="surface-title">明确不测范围</h2>
        <div class="mission-body"><ul class="chips"><li v-for="item in detail.untested_scope" :key="item" class="chip off">✗ {{ item }}</li><li v-if="!detail.untested_scope.length" class="muted">—</li></ul></div>
      </section>
    </div>
    <section class="surface mission-block">
      <h2 class="surface-title">执行信息</h2>
      <div class="mission-body kv">
        <span>状态</span><b>{{ detail.state }}</b>
        <span>测试强度</span><b>{{ detail.mission.strategy }}</b>
        <span>预计规模</span><b>约 {{ detail.estimate.case_min }}~{{ detail.estimate.case_max }} Case · {{ detail.estimate.sql_min }}~{{ detail.estimate.sql_max }} SQL</b>
        <span>验收目标</span><b>{{ detail.mission.acceptance_goal }}</b>
        <span v-if="detail.mission.job_id">关联任务</span>
        <b v-if="detail.mission.job_id"><RouterLink class="link" :to="`/jobs/${detail.mission.job_id}`">查看任务 {{ shortId(detail.mission.job_id) }}</RouterLink></b>
      </div>
      <p class="hint">Query / 当前定义范围 与 Query 全模块验收分开；模块层面仍为 {{ detail.completeness_note }}。</p>
    </section>
  </template>

  <section v-else class="surface">
    <div class="table-scroll"><table class="data-table">
      <thead><tr><th>测试目标</th><th>范围</th><th>强度</th><th>状态</th><th>关联任务</th></tr></thead>
      <tbody><tr v-for="item in missions" :key="item.mission_id">
        <td><RouterLink class="link" :to="`/tests/${item.mission_id}`">{{ item.name || item.mission_id }}</RouterLink></td>
        <td>{{ item.features.join(' / ') || '—' }}</td><td>{{ item.strategy }}</td><td>{{ item.state }}</td>
        <td><RouterLink v-if="item.job_id" class="link" :to="`/jobs/${item.job_id}`">{{ shortId(item.job_id) }}</RouterLink><span v-else class="muted">—</span></td>
      </tr></tbody>
    </table></div>
    <p v-if="loading" class="empty-state">正在读取测试目标…</p>
    <p v-else-if="!missions.length" class="empty-state">尚无测试目标。<RouterLink class="link" to="/tests/new">创建一个 →</RouterLink></p>
  </section>
</template>

<style scoped>
.mission-block { overflow: hidden; margin-bottom: 16px; }
.mission-body { padding: 18px 20px; }
.mission-two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.narrative { margin: 0; white-space: pre-wrap; font-size: 14px; color: #23354f; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
.chip { padding: 5px 10px; border-radius: 5px; font-size: 13px; font-weight: 600; }
.chip.ok { color: #17834b; background: #e7f5ed; }
.chip.off { color: #68778b; background: #eef1f5; }
.kv { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 10px 18px; font-size: 13px; }
.kv span { color: var(--muted); }
.kv b { color: #23354f; }
.hint { margin: 0; padding: 0 20px 18px; color: var(--muted); font-size: 12px; }
.create-link { white-space: nowrap; }
@media (max-width: 900px) { .mission-two { grid-template-columns: 1fr; } }
</style>
