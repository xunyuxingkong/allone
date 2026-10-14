<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getMission, listMissions, retryMissionFeature, startMission, type MissionSummary, type MissionView } from '../api/missions'
import { shortId } from '../utils'

const route = useRoute()
const missionId = computed(() => route.params.missionId as string | undefined)
const missions = ref<MissionSummary[]>([])
const detail = ref<MissionView | null>(null)
const loading = ref(false)
const error = ref('')
const retryingFeature = ref('')
const startingMission = ref(false)

const BLOCKER_HELP: Record<string, { title: string; reason: string; nextStep: string }> = {
  DATABASE_CONFIG_MISSING: {
    title: '数据库连接信息未配置',
    reason: '当前任务无法读取完整的数据库连接配置。',
    nextStep: '检查运行环境中的数据库地址、端口、数据库名和账号配置，再重新执行 Preflight。',
  },
  DATABASE_NETWORK_UNREACHABLE: {
    title: '数据库暂时无法连接',
    reason: 'Core 未能连接到配置的 Xugu 数据库。',
    nextStep: '检查网络连通性、服务地址和端口；确认数据库可用后重新执行 Preflight。',
  },
  DATABASE_EXECUTOR_UNSUPPORTED: {
    title: '当前执行环境不支持数据库操作',
    reason: '任务所在的执行环境没有可用的 Xugu 数据库执行器。',
    nextStep: '在配置了项目 Python 驱动的执行环境中重新运行任务。',
  },
  DATABASE_WORKER_UNAVAILABLE: {
    title: '数据库执行工作进程不可用',
    reason: 'Core 无法启动或连接数据库执行工作进程。',
    nextStep: '检查本地数据库 Worker 服务后重试；不要把本次状态当作数据库测试结果。',
  },
  DATABASE_WORKER_FAILED: {
    title: '数据库执行工作进程异常退出',
    reason: '执行 Worker 未能正常返回 Preflight 结果。',
    nextStep: '检查 Worker 错误日志，修复执行环境后重新运行。',
  },
  RUNTIME_PROFILE_STALE: {
    title: '运行时配置与当前环境不匹配',
    reason: '当前数据库或执行合同与已记录的 Runtime Profile 不一致。',
    nextStep: '重新采集 Runtime Probe 和数据库 build 信息，再使用最新 Runtime Profile 运行。',
  },
  RUNTIME_PROFILE_UNAVAILABLE: {
    title: '缺少有效的运行时配置',
    reason: 'Core 找不到可用于本次数据库执行的 Runtime Profile。',
    nextStep: '完成 Runtime Probe 并配置对应 Profile 后重新执行。',
  },
  SIGNED_APPROVAL_NOT_CONFIGURED: {
    title: '等待负责人签名审批',
    reason: 'AI 和网页不会代替负责人签署审批文件。',
    nextStep: '请负责人核对候选、覆盖和运行环境，再按下方步骤在本地完成签名与验签。',
  },
  HUMAN_REVIEW_AND_SIGNED_APPROVAL_REQUIRED: {
    title: '人工评审与签名审批尚未完成',
    reason: '当前证据仍处于人工治理门禁，不能直接晋升。',
    nextStep: '完成候选人工评审，并由授权负责人签署当前 Manifest 与 Promotion Plan。',
  },
  PACKAGE_INTEGRITY_FAILED: {
    title: '验收材料完整性校验未通过',
    reason: '冻结包中的证据、索引或绑定关系存在缺失或不一致。',
    nextStep: '按下方详细阻断项修复输入，再重新生成并核验验收材料。',
  },
  JOB_ABANDONED_BY_OPERATOR: {
    title: '任务已由操作人员停止',
    reason: '此状态表示任务被主动放弃，不代表数据库用例执行失败。',
    nextStep: '如仍需完成本轮测试，请重新启动任务或创建新的测试目标。',
  },
}

function blockerHelp(code: string) {
  return BLOCKER_HELP[code] ?? {
    title: '需要处理的门禁项',
    reason: 'Core 报告了一个阻止任务继续的条件。',
    nextStep: '根据高级信息中的错误码检查对应证据；修复后重新执行相关步骤。',
  }
}

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

async function retryFeature(feature: string) {
  if (!missionId.value || retryingFeature.value) return
  retryingFeature.value = feature
  error.value = ''
  try { detail.value = await retryMissionFeature(missionId.value, feature) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '无法重跑此 Feature' }
  finally { retryingFeature.value = '' }
}

async function continueMission() {
  if (!missionId.value || startingMission.value) return
  startingMission.value = true
  error.value = ''
  try { detail.value = await startMission(missionId.value) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '无法继续创建 Feature 子任务' }
  finally { startingMission.value = false }
}

const featureLabel = (feature: string) => ({
  join: 'JOIN', filter: 'Filter', aggregate: 'Aggregate', subquery: 'Subquery', sort_limit: 'Sort / Limit',
} as Record<string, string>)[feature] ?? feature
const jobStateLabel = (state: string) => ({
  PLANNED: '待执行', RUNNING: '运行中', WAITING_APPROVAL: '等待审批',
  BLOCKED: '已阻断', FAILED: '失败', COMPLETED: '已完成',
} as Record<string, string>)[state] ?? state
// List and detail share one component, so navigate reuses the instance; watch the param.
watch(() => route.params.missionId, refresh)
onMounted(refresh)
</script>

<template>
  <div class="page-heading">
    <div><RouterLink v-if="missionId" class="link" to="/tests">← 测试目标</RouterLink><h1>{{ detail ? detail.mission.name : '测试目标' }}</h1>
      <p>测试目标 → 测试任务 → 运行记录。测试目标说明为什么测、测什么、不测什么。</p></div>
    <RouterLink class="link create-link" to="/tests/new">＋ 创建测试任务</RouterLink>
    <button v-if="missionId" class="control refresh-mission" :disabled="loading" @click="refresh">刷新状态</button>
    <button v-if="detail && detail.feature_summary.started_features < detail.feature_summary.requested_features" class="control refresh-mission" :disabled="startingMission" @click="continueMission">{{ startingMission ? '正在继续…' : '继续创建剩余 Feature' }}</button>
  </div>
  <div v-if="error" class="error-banner" role="alert">{{ error }}</div>

  <template v-if="detail">
    <section class="surface mission-block">
      <h2 class="surface-title">测试目的</h2>
      <div class="mission-body"><p class="narrative">{{ detail.mission.purpose }}</p></div>
    </section>
    <div class="mission-two">
      <section class="surface mission-block">
        <h2 class="surface-title">请求的测试范围</h2>
        <div class="mission-body">
          <ul class="chips"><li v-for="item in detail.requested_scope" :key="item" class="chip">{{ item }}</li><li v-if="!detail.requested_scope.length" class="muted">—</li></ul>
          <p>已执行：{{ detail.executed_scope.join(' / ') || '尚无执行证据' }}</p>
          <p>已覆盖：{{ detail.covered_scope.join(' / ') || '尚未达到完整覆盖' }}</p>
          <RouterLink class="link" :to="`/tests/${detail.mission.mission_id}/scope`">查看测试空间矩阵 →</RouterLink>
        </div>
      </section>
      <section class="surface mission-block">
        <h2 class="surface-title">明确不测范围</h2>
        <div class="mission-body"><ul class="chips"><li v-for="item in detail.excluded_scope" :key="item" class="chip off">✗ {{ item }}</li><li v-if="!detail.excluded_scope.length" class="muted">—</li></ul></div>
      </section>
    </div>
    <section class="surface mission-block">
      <h2 class="surface-title">执行信息</h2>
      <div class="mission-body kv">
        <span>状态</span><b>{{ detail.state }}</b>
        <span>测试强度</span><b>{{ detail.mission.strategy }}</b>
        <span>预计规模</span><b>约 {{ detail.estimate.case_min }}~{{ detail.estimate.case_max }} Case · {{ detail.estimate.sql_min }}~{{ detail.estimate.sql_max }} SQL</b>
        <span>验收目标</span><b>{{ detail.mission.acceptance_goal }}</b>
        <template v-if="detail.mission.strategy === 'SMOKE'">
          <span>Smoke 生成进度</span><b>{{ detail.generation_progress.generated_total }} / {{ detail.generation_progress.budget ?? '—' }} 候选 · 剩余 {{ detail.generation_progress.remaining_budget ?? '—' }}</b>
          <span>Smoke 阶段</span><b>{{ detail.generation_progress.smoke_complete ? '已完成（不代表 Pairwise 覆盖完成或已晋升）' : '未完成' }} · Regression {{ detail.generation_progress.regression_pass ? 'PASS' : '未通过' }} · 候选证据 {{ detail.generation_progress.generated_cases_valid ? '有效' : '未齐' }}</b>
          <span>覆盖目标</span><b>{{ detail.generation_progress.pairwise_complete ? 'Pairwise 已完整覆盖' : detail.generation_progress.coverage_target === 'SMOKE_BUDGET_OR_NO_GAP' ? '预算耗尽或无可生成缺口；不代表 Pairwise 完成' : detail.generation_progress.coverage_target }}</b>
        </template>
        <span v-if="detail.mission.job_id">首个子任务</span>
        <b v-if="detail.mission.job_id"><RouterLink class="link" :to="`/jobs/${detail.mission.job_id}`">查看任务 {{ shortId(detail.mission.job_id) }}</RouterLink></b>
      </div>
      <p class="hint">Query / 当前定义范围 与 Query 全模块验收分开；模块层面仍为 {{ detail.completeness_note }}。</p>
      <p v-if="!detail.execution_policy.data_scale_applied || !detail.execution_policy.risk_focus_applied" class="hint">数据规模和风险重点已记录，但当前生成器尚未据此调整数据集或候选选择。</p>
    </section>

    <section v-if="detail.feature_jobs.length" class="surface mission-block child-jobs">
      <h2 class="surface-title">Feature 子任务</h2>
      <div class="mission-body">
        <div class="feature-summary">
          <span><b>{{ detail.feature_summary.completed_features }}</b> / {{ detail.feature_summary.requested_features }} 个 Feature 已完成</span>
          <span>{{ detail.feature_summary.case_count }} Cases · {{ detail.feature_summary.sql_count }} SQL</span>
          <span class="text-fail">{{ detail.feature_summary.failure_count }} 个失败</span>
          <span>{{ detail.feature_summary.candidate_count }} 个候选 · {{ detail.feature_summary.ai_findings_count }} 条 AI 发现</span>
        </div>
        <article v-for="item in detail.feature_jobs" :key="`${item.feature}:${item.attempt}`" class="feature-job-card" :class="{ historical: !item.is_latest }">
          <div class="feature-job-head">
            <div><b>{{ featureLabel(item.feature) }}</b><span class="muted">第 {{ item.attempt }} 次执行{{ item.is_latest ? ' · 当前' : ' · 历史' }}</span></div>
            <span class="mission-job-state" :class="`state-${item.state.toLowerCase()}`">{{ jobStateLabel(item.state) }}</span>
          </div>
          <div class="feature-job-metrics">
            <span>Case：{{ item.case_count ?? '尚未回归' }}</span>
            <span>SQL：{{ item.sql_count ?? '尚未回归' }}</span>
            <span>失败：{{ item.failure_count ?? '—' }}</span>
            <span>候选：{{ item.candidate_count }}</span>
            <span>覆盖：{{ item.coverage ? `${item.coverage.active_covered ?? 0} / ${item.coverage.required ?? '—'} · 缺口 ${item.coverage.active_missing ?? '—'}` : '尚无覆盖证据' }}</span>
            <span>审批：{{ item.approval_status }}</span>
            <span>AI 发现：{{ item.ai_findings_count }}</span>
          </div>
          <ul v-if="item.blockers.length" class="child-blockers"><li v-for="blocker in item.blockers" :key="blocker">{{ blocker }}</li></ul>
          <div class="feature-job-actions">
            <RouterLink class="link" :to="`/jobs/${item.job_id}`">查看子任务 {{ shortId(item.job_id) }} →</RouterLink>
            <button v-if="item.is_latest && ['BLOCKED', 'FAILED'].includes(item.state)" class="retry-button" :disabled="!!retryingFeature" @click="retryFeature(item.feature)">{{ retryingFeature === item.feature ? '正在创建…' : '重跑此 Feature' }}</button>
          </div>
        </article>
      </div>
    </section>

    <section v-if="detail.approval_review.evidence?.blockers?.length" class="surface mission-block blocker-list" aria-label="当前待处理事项">
      <h2 class="surface-title">当前待处理</h2>
      <div class="mission-body">
        <article v-for="item in detail.approval_review.evidence.blockers" :key="item" class="blocker-card">
          <b>{{ blockerHelp(item).title }}</b>
          <p>{{ blockerHelp(item).reason }}</p>
          <p><strong>建议：</strong>{{ blockerHelp(item).nextStep }}</p>
          <details><summary>高级信息</summary><code>{{ item }}</code></details>
        </article>
      </div>
    </section>

    <section v-if="detail.approval_review.status !== 'NOT_READY'" class="surface mission-block approval-block">
      <h2 class="surface-title">人工审批与签名</h2>
      <div class="mission-body">
        <p class="approval-status">{{ detail.approval_review.status === 'APPROVED_CURRENT' ? '当前签名与审批输入已通过 Core 只读复核。' : detail.approval_review.status === 'APPROVED_STALE' ? '历史签名曾通过，但当前审批输入已变化或无法验证，请重新核验。' : detail.approval_review.status === 'INVALID' ? '审批证据无法读取，请检查冻结审批包。' : '测试证据已进入人工审批门禁。AI 不会代替负责人签名。' }}</p>
        <p v-if="detail.approval_review.reason" class="muted">{{ detail.approval_review.reason }}</p>
        <p v-if="detail.mission.features.length > 1" class="hint">父 Mission 汇总各 Feature 的审批状态；每个子任务拥有独立 Manifest 与 Promotion Plan。请打开对应的 Feature 子任务分别核对其审批材料。</p>
        <template v-if="detail.mission.features.length === 1">
        <div class="approval-grid">
          <div><span>审批包</span><b class="mono">{{ detail.approval_review.manifest_id || '尚未冻结' }}</b></div>
          <div><span>Promotion Plan</span><b class="mono">{{ detail.approval_review.plan_hash || '尚未冻结' }}</b></div>
          <div><span>候选数</span><b>{{ detail.approval_review.candidate_count ?? '—' }}</b></div>
          <div><span>Runtime Profile</span><b class="mono">{{ detail.approval_review.runtime_profile_id || '—' }}</b></div>
          <div><span>数据库版本 / Build</span><b>{{ detail.approval_review.database_version || '—' }} / {{ detail.approval_review.database_build_time || '—' }}</b></div>
          <div><span>执行合同</span><b class="mono">{{ detail.approval_review.contract_bindings?.execution || '—' }}</b></div>
          <div><span>技术评审记录</span><b>{{ detail.approval_review.technical_review_count ?? 0 }}</b></div>
          <div><span>验收就绪状态</span><b>{{ detail.approval_review.readiness || '等待审批材料' }}</b></div>
          <div><span>Regression</span><b>{{ detail.approval_review.evidence?.regression_status || 'NOT_RUN' }} · 失败 {{ detail.approval_review.evidence?.regression_failures ?? 0 }}</b></div>
          <div><span>Trial 双跑</span><b>{{ detail.approval_review.evidence?.trial_status || 'INCOMPLETE' }} · {{ detail.approval_review.evidence?.trial_double_run_pass_count ?? 0 }}</b></div>
          <div><span>Mutation</span><b>已杀死 {{ detail.approval_review.evidence?.mutation_killed_count ?? 0 }}</b></div>
          <div><span>覆盖</span><b>正式 {{ detail.approval_review.coverage?.active_covered ?? '—' }} / 缺口 {{ detail.approval_review.coverage?.active_missing ?? '—' }} · 晋升后缺口 {{ detail.approval_review.coverage?.provisional_missing ?? '—' }}</b></div>
        </div>
        <div v-if="detail.approval_review.manifest_ref && detail.approval_review.plan_ref" class="approval-artifacts">
          <div><span>冻结 Manifest</span><code>{{ detail.approval_review.manifest_ref }}</code></div>
          <div><span>Promotion Plan</span><code>{{ detail.approval_review.plan_ref }}</code></div>
        </div>
        <p class="hint inline-hint">负责人应先核对 Mission、候选、覆盖缺口、运行环境、合同版本和技术评审，再使用本地 Operator CLI 签署绑定当前 Manifest 与 Plan 的审批文件。私钥只在本地签名命令中使用，不上传到网页或发送给 AI。</p>
        <ol class="approval-steps">
          <li>如未配置签名人，在项目外安全位置初始化本地密钥并登记公钥：<code>xgtest approval signer-init --principal "负责人标识" --private-key "项目外私钥路径" --allowed-signers "Allowed Signers 路径"</code>（会由 ssh-keygen 交互式提示设置私钥口令）。</li>
          <li>准备签名载荷：<code>xgtest approval prepare --manifest "{{ detail.approval_review.manifest_ref }}" --plan "{{ detail.approval_review.plan_ref }}" --principal "负责人标识" --output "审批目录/payload.json"</code></li>
          <li>负责人核对载荷后本地签名：<code>xgtest approval sign --payload "审批目录/payload.json" --manifest "{{ detail.approval_review.manifest_ref }}" --plan "{{ detail.approval_review.plan_ref }}" --private-key "项目外私钥路径" --output "审批目录/approval.json"</code></li>
          <li>先用 Core 验签，再配置审批文件和 Allowed Signers 并恢复任务：<code>xgtest approval verify --approval "审批目录/approval.json" --allowed-signers "Allowed Signers 路径" --manifest "{{ detail.approval_review.manifest_ref }}" --plan "{{ detail.approval_review.plan_ref }}"</code>。随后设置 XGTEST_APPROVAL / XGTEST_ALLOWED_SIGNERS，resume 后由 Core 执行 preflight；签名无效、过期或输入变化都会拒绝。</li>
        </ol>
        </template>
        <details v-if="detail.mission.features.length === 1 && detail.approval_review.technical_reviews?.length" class="approval-review-list">
          <summary>查看 AI 技术评审内容（仅供负责人参考）</summary>
          <article v-for="(review, index) in detail.approval_review.technical_reviews" :key="`${review.case_id}-${index}`">
            <b>{{ review.case_id }} · {{ review.decision }} · {{ review.recommendation }}</b>
            <ul><li v-for="finding in review.findings" :key="finding">{{ finding }}</li></ul>
          </article>
        </details>
        <p v-if="detail.approval_review.untested_scope?.length" class="muted">当前仍有未完整覆盖范围：{{ detail.approval_review.untested_scope.join(' / ') }}</p>
      </div>
    </section>

    <section class="surface mission-block ai-block">
      <h2 class="surface-title">AI 测试分析</h2>
      <template v-if="detail.ai_summary.available">
        <div class="mission-body">
          <p v-if="detail.ai_summary.summary" class="narrative">{{ detail.ai_summary.summary }}</p>
          <p v-else class="muted">本轮尚未产生 AI 分析文本。</p>
          <div class="ai-stats">
            <span><b>{{ detail.ai_summary.generated_candidate_count ?? 0 }}</b> AI 生成候选</span>
            <span><b>{{ detail.ai_summary.technical_review_count ?? 0 }}</b> AI 技术评审</span>
            <span v-if="detail.ai_summary.technical_review_decisions">决策 PASS {{ detail.ai_summary.technical_review_decisions.PASS }} · CONCERNS {{ detail.ai_summary.technical_review_decisions.CONCERNS }} · FAIL {{ detail.ai_summary.technical_review_decisions.FAIL }}</span>
          </div>
          <div v-if="detail.ai_summary.failure_analysis" class="ai-failure">
            <div class="failure-head"><b>AI 失败分析</b><span class="muted">{{ detail.ai_summary.failure_analysis.category }} · 置信度 {{ detail.ai_summary.failure_analysis.confidence }}</span></div>
            <div class="origin-meta">
              <div><span>现象</span><b>{{ detail.ai_summary.failure_analysis.failure_summary }}</b></div>
              <div><span>可能区域</span><b>{{ detail.ai_summary.failure_analysis.likely_area }}</b></div>
              <div><span>建议动作</span><b>{{ detail.ai_summary.failure_analysis.recommended_action }}</b></div>
            </div>
          </div>
          <p class="hint">以上为 AI 建议，不改变 Core 判定；PASS/FAIL、覆盖与验收仍由 Core 决定。</p>
        </div>
      </template>
      <p v-else class="mission-empty">{{ detail.ai_summary.note }}</p>
    </section>
  </template>

  <section v-else class="surface">
    <div class="table-scroll"><table class="data-table">
      <thead><tr><th>测试目标</th><th>范围</th><th>强度</th><th>状态</th><th>子任务</th></tr></thead>
      <tbody><tr v-for="item in missions" :key="item.mission_id">
        <td><RouterLink class="link" :to="`/tests/${item.mission_id}`">{{ item.name || item.mission_id }}</RouterLink></td>
        <td>{{ item.features.map(featureLabel).join(' / ') || '—' }}</td><td>{{ item.strategy }}</td><td>{{ item.state }}</td>
        <td><RouterLink v-if="item.job_id" class="link" :to="`/tests/${item.mission_id}`">{{ item.feature_job_count ?? 1 }} 个 · 查看</RouterLink><span v-else class="muted">尚未启动</span></td>
      </tr></tbody>
    </table></div>
    <p v-if="loading" class="empty-state">正在读取测试目标…</p>
    <p v-else-if="!missions.length" class="empty-state">尚无测试目标。<RouterLink class="link" to="/tests/new">创建一个 →</RouterLink></p>
  </section>
</template>

<style scoped>
.mission-block { overflow: hidden; margin-bottom: 16px; }
.mission-body { display: grid; gap: 12px; padding: 18px 20px; }
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
.ai-block .narrative { white-space: pre-wrap; }
.approval-block { border-color: #d7c48a; }
.approval-status { margin: 0; font-weight: 700; color: #614600; }
.approval-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.approval-grid > div { display: grid; min-width: 0; gap: 5px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 6px; }
.approval-grid span { color: var(--muted); font-size: 11px; }
.approval-grid b { overflow-wrap: anywhere; font-size: 12px; }
.approval-artifacts { display: grid; gap: 8px; font-size: 12px; }
.approval-artifacts > div { display: grid; gap: 4px; }
.approval-artifacts code, .approval-steps code { overflow-wrap: anywhere; padding: 3px 5px; border-radius: 4px; background: #f1f3f7; color: #33445e; font-size: 11px; }
.approval-steps { display: grid; gap: 8px; margin: 0; padding-left: 20px; font-size: 12px; color: #52627a; }
.blocker-list .mission-body { gap: 9px; }
.blocker-list > .surface-title { color: #7e2e2e; }
.blocker-card { display: grid; gap: 6px; padding: 11px 13px; border: 1px solid #e8c6c2; border-left: 3px solid #b5473d; border-radius: 6px; background: #fff9f8; font-size: 12px; }
.blocker-card > b { color: #7e2e2e; }
.blocker-card p { margin: 0; color: #5c5360; line-height: 1.5; }
.blocker-card strong { color: #3f4650; }
.blocker-card details { margin-top: 2px; color: var(--muted); }
.blocker-card summary { width: fit-content; cursor: pointer; font-size: 11px; }
.blocker-card code { display: inline-block; margin-top: 5px; overflow-wrap: anywhere; padding: 3px 5px; border-radius: 4px; background: #f1f3f7; color: #33445e; font-size: 11px; }
.approval-review-list { border-top: 1px solid var(--line); padding-top: 10px; font-size: 12px; }
.approval-review-list summary { cursor: pointer; font-weight: 700; }
.approval-review-list article { display: grid; gap: 5px; margin-top: 10px; padding: 10px; background: #f7f9fc; border-radius: 5px; }
.approval-review-list ul { display: grid; gap: 3px; margin: 0; padding-left: 18px; }
.feature-summary { display: flex; flex-wrap: wrap; gap: 10px 22px; padding: 12px 14px; border-radius: 6px; background: #f4f7fb; color: #4c5d73; font-size: 12px; }
.refresh-mission { width: auto; cursor: pointer; }
.feature-summary b { color: #1e4fae; }
.feature-job-card { display: grid; gap: 11px; padding: 14px; border: 1px solid var(--line); border-radius: 7px; background: #fff; }
.feature-job-card.historical { background: #f8f9fb; }
.feature-job-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.feature-job-head > div { display: grid; gap: 4px; }
.feature-job-head .muted { font-size: 11px; }
.mission-job-state { display: inline-flex; align-items: center; padding: 4px 9px; border-radius: 12px; background: #eef1f5; color: #58677b; font-size: 11px; font-weight: 700; white-space: nowrap; }
.mission-job-state.state-running, .mission-job-state.state-planned { background: #e9f1ff; color: #2459a6; }
.mission-job-state.state-waiting_approval { background: #fff5d9; color: #805900; }
.mission-job-state.state-completed { background: #e7f5ed; color: #17834b; }
.mission-job-state.state-blocked, .mission-job-state.state-failed { background: #fdecea; color: #a12b25; }
.feature-job-metrics { display: flex; flex-wrap: wrap; gap: 8px 18px; color: #52627a; font-size: 12px; }
.child-blockers { display: grid; gap: 4px; margin: 0; padding-left: 18px; color: #9b2c2c; font-size: 12px; }
.feature-job-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
.retry-button { min-height: 32px; padding: 0 11px; border: 1px solid #bb726b; border-radius: 5px; background: #fff; color: #8a342c; font-size: 12px; cursor: pointer; }
.retry-button:disabled { opacity: .6; cursor: default; }
.inline-hint { padding: 0; }
.ai-stats { display: flex; flex-wrap: wrap; gap: 8px 30px; font-size: 13px; color: #23354f; }
.ai-stats b { font-size: 18px; font-weight: 700; }
.ai-failure { display: grid; gap: 10px; padding: 14px 16px; border: 1px solid var(--line); border-radius: 6px; background: #f9fbfe; }
.failure-head { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
.failure-head .muted { font-size: 11px; }
.origin-meta { display: grid; gap: 8px; font-size: 13px; }
.origin-meta > div { display: grid; grid-template-columns: 80px minmax(0, 1fr); gap: 14px; }
.origin-meta span { color: var(--muted); }
.origin-meta b { color: #23354f; font-weight: 600; overflow-wrap: anywhere; }
@media (max-width: 900px) { .mission-two { grid-template-columns: 1fr; } }
</style>
