<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createMission, startMission, type MissionDefinition, type MissionStrategy } from '../api/missions'

const router = useRouter()

// Only features the Core can model today are enabled; the rest fail closed.
const FEATURES = [
  { value: 'join', label: 'JOIN', enabled: true },
  { value: 'filter', label: 'Filter / WHERE', enabled: true },
  { value: 'aggregate', label: 'Aggregate / GROUP BY', enabled: true },
  { value: 'subquery', label: 'Subquery', enabled: true },
  { value: 'sort_limit', label: 'Sort / Limit', enabled: true },
  { value: 'window', label: 'Window', enabled: false },
  { value: 'cte', label: 'CTE', enabled: false },
  { value: 'set_operation', label: 'Set Operation', enabled: false },
]
const RISK_FOCUS = ['null', 'duplicate', 'boundary', 'type_conversion']
const EXCLUDED_SCOPE = ['performance', 'concurrency', 'transaction', 'window', 'cte']
const STRATEGIES: { value: MissionStrategy; label: string; detail: string }[] = [
  { value: 'SMOKE', label: 'Smoke', detail: 'Pairwise，最多生成 30 个候选' },
  { value: 'STANDARD', label: 'Standard', detail: 'Pairwise 全部要求组合' },
  { value: 'FULL', label: 'Full', detail: 'All Values 覆盖策略' },
  { value: 'AI_EXPLORATORY', label: 'AI Exploratory', detail: 'Standard 基线与 AI 风险简报；自动补测循环尚未实现' },
]

const form = reactive({
  name: 'Query 语义正确性标准测试',
  purpose: '验证当前 Xugu Build 下 Query 模块核心语义正确性',
  features: ['join'] as string[],
  strategy: 'STANDARD' as MissionStrategy,
  data_scale: 'SMALL' as MissionDefinition['data_scale'],
  risk_focus: ['null', 'duplicate'] as string[],
  acceptance_goal: '本期定义范围内语义正确',
  excluded_scope: ['performance', 'concurrency', 'transaction'] as string[],
})

const submitting = ref(false)
const error = ref('')
const toggle = (list: string[], value: string) => {
  const index = list.indexOf(value)
  if (index >= 0) list.splice(index, 1)
  else list.push(value)
}
const estimate = computed(() => {
  const featureRanges: Record<string, [number, number]> = {
    join: [40, 60], filter: [40, 70], aggregate: [30, 60], subquery: [30, 60], sort_limit: [20, 40],
  }
  const standard = featureRanges[form.features[0] ?? 'join'] ?? [0, 0]
  const ranges: Record<MissionStrategy, [number, number]> = {
    SMOKE: [0, 30], STANDARD: standard, FULL: [500, 2000], AI_EXPLORATORY: standard,
  }
  const [min, max] = ranges[form.strategy]
  return { min, max, sqlMin: min, sqlMax: max * 2 }
})
async function submit() {
  error.value = ''
  if (!form.features.length) { error.value = '请至少选择一个测试范围。'; return }
  if (!form.name.trim() || !form.purpose.trim()) { error.value = '测试目的不能为空。'; return }
  submitting.value = true
  try {
    const created = await createMission({ ...form, risk_focus: [...form.risk_focus], excluded_scope: [...form.excluded_scope] })
    const started = await startMission(created.mission.mission_id)
    const jobId = started.mission.job_id
    router.push(jobId ? `/jobs/${jobId}` : `/tests/${created.mission.mission_id}`)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '创建测试任务失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page-heading">
    <div><h1>创建测试任务</h1><p>先说明为什么测、测什么、不测什么，再启动 AI 测试。</p></div>
    <span class="heading-meta">Test Mission</span>
  </div>
  <div v-if="error" class="error-banner" role="alert">{{ error }}</div>

  <div class="mission-form">
    <section class="surface mission-block">
      <h2 class="surface-title">① 测试目的</h2>
      <div class="mission-body">
        <label class="field"><span>任务名称</span><input v-model="form.name" class="control" maxlength="200" /></label>
        <label class="field"><span>测试目的</span><textarea v-model="form.purpose" class="control textarea" rows="3" maxlength="2000"></textarea></label>
      </div>
    </section>

    <section class="surface mission-block">
      <h2 class="surface-title">② 测试范围</h2>
      <div class="mission-body">
        <div class="option-grid">
          <label v-for="feature in FEATURES" :key="feature.value" class="option" :class="{ disabled: !feature.enabled }">
            <input type="radio" name="mission-feature" :value="feature.value" v-model="form.features[0]" :disabled="!feature.enabled" />
            <span>{{ feature.label }}</span>
            <em v-if="!feature.enabled">未支持</em>
          </label>
        </div>
        <p class="hint">每个 Job 当前执行一个 Feature。多 Feature Mission 编排上线前，请为本次任务选择单一测试范围。</p>
      </div>
    </section>

    <section class="surface mission-block">
      <h2 class="surface-title">③ 测试强度</h2>
      <div class="mission-body">
        <label v-for="item in STRATEGIES" :key="item.value" class="option wide">
          <input type="radio" :value="item.value" v-model="form.strategy" />
          <span>{{ item.label }}</span><em>{{ item.detail }}</em>
        </label>
      </div>
    </section>

    <div class="mission-columns">
      <section class="surface mission-block">
        <h2 class="surface-title">④ 风险重点</h2>
        <div class="mission-body option-grid">
          <label v-for="item in RISK_FOCUS" :key="item" class="option"><input type="checkbox" :checked="form.risk_focus.includes(item)" @change="toggle(form.risk_focus, item)" /><span>{{ item }}</span></label>
        </div>
      </section>
      <section class="surface mission-block">
        <h2 class="surface-title">⑤ 数据规模</h2>
        <div class="mission-body option-grid">
          <label v-for="scale in (['SMALL','MEDIUM','LARGE'] as const)" :key="scale" class="option"><input type="radio" :value="scale" v-model="form.data_scale" /><span>{{ scale }}</span></label>
        </div>
      </section>
    </div>

    <section class="surface mission-block">
      <h2 class="surface-title">⑥ 预计测试规模</h2>
      <div class="mission-body estimate">
        <span>约 {{ estimate.min }}~{{ estimate.max }} 个 Case</span>
        <span>约 {{ estimate.sqlMin }}~{{ estimate.sqlMax }} 次 SQL 执行</span>
        <span>模式：{{ form.strategy }}</span>
      </div>
    </section>

    <section class="surface mission-block">
      <h2 class="surface-title">⑦ 明确不测范围</h2>
      <div class="mission-body option-grid">
        <label v-for="item in EXCLUDED_SCOPE" :key="item" class="option"><input type="checkbox" :checked="form.excluded_scope.includes(item)" @change="toggle(form.excluded_scope, item)" /><span>{{ item }}</span></label>
      </div>
    </section>

    <div class="mission-actions">
      <button class="control primary-action" :disabled="submitting" @click="submit">{{ submitting ? '正在启动…' : '⑧ 启动 AI 测试' }}</button>
    </div>
  </div>
</template>

<style scoped>
.mission-form { display: grid; gap: 16px; }
.mission-block { overflow: hidden; }
.mission-body { display: grid; gap: 14px; padding: 18px 20px; }
.mission-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.field { display: grid; gap: 7px; }
.field > span { color: var(--muted); font-size: 12px; font-weight: 700; }
.textarea { height: auto; padding: 9px 11px; resize: vertical; }
.option-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
.option { display: flex; align-items: center; gap: 9px; padding: 9px 11px; border: 1px solid var(--line); border-radius: 6px; font-size: 13px; cursor: pointer; }
.option.wide { gap: 12px; }
.option em { color: var(--muted); font-size: 11px; font-style: normal; }
.option.disabled { opacity: .55; cursor: not-allowed; }
.estimate { grid-auto-flow: column; justify-content: start; gap: 30px; font-size: 14px; font-weight: 700; color: #23354f; }
.hint { margin: 0; color: var(--muted); font-size: 12px; }
.mission-actions { display: flex; justify-content: flex-end; }
.primary-action { width: auto; min-width: 190px; height: 42px; border-color: #17499d; background: #1e4fae; color: #fff; font-weight: 700; cursor: pointer; }
.primary-action:disabled { opacity: .7; cursor: default; }
@media (max-width: 900px) { .mission-columns { grid-template-columns: 1fr; } .estimate { grid-auto-flow: row; gap: 8px; } }
</style>
