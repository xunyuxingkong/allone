<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { getCase } from '../api/runs'
import type { CaseDetailResponse } from '../types'
import StatusTag from '../components/StatusTag.vue'
import SqlViewer from '../components/SqlViewer.vue'
import { formatDuration, shortId } from '../utils'

const props = defineProps<{ runId: string; caseId: string }>()
const detail = ref<CaseDetailResponse | null>(null)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await getCase(props.runId, props.caseId)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法读取 Case 详情'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => [props.runId, props.caseId], load)
</script>

<template>
  <div class="back-row">
    <RouterLink class="link" :to="`/runs/${runId}`">← 返回 Run {{ shortId(runId, 12) }}</RouterLink>
  </div>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <template v-if="detail">
    <div class="page-heading case-heading">
      <div>
        <h1>{{ detail.report.title ?? detail.report.case_id }}</h1>
        <p class="mono">{{ detail.report.case_id }}</p>
      </div>
      <StatusTag :status="detail.report.status" />
    </div>

    <div class="detail-stack">
      <section class="surface">
        <h2 class="surface-title">用例元数据</h2>
        <div class="detail-body detail-kv">
          <span class="key">Case ID</span><span class="mono">{{ detail.report.case_id }}</span>
          <span class="key">Title</span><span>{{ detail.report.title ?? '—' }}</span>
          <span class="key">Feature</span><span>{{ detail.report.feature ?? '—' }}</span>
          <span class="key">Tags</span><span>{{ detail.report.tags.join(' · ') || '—' }}</span>
          <span class="key">Status</span><span><StatusTag :status="detail.report.status" /></span>
          <span class="key">Failure Type</span><span class="mono">{{ detail.report.failure_type ?? '—' }}</span>
          <span class="key">Duration</span><span>{{ formatDuration(detail.report.duration_ms) }}</span>
          <span class="key">Source File</span><span class="mono">{{ detail.report.source_file ?? '—' }}</span>
          <span class="key">Source SHA-256</span><span class="digest">{{ detail.report.case_source_hash ?? '—' }}</span>
          <span class="key">Git Commit</span><span class="mono">{{ detail.git_commit ?? '—' }}</span>
        </div>
      </section>

      <template v-if="detail.source_available && detail.case_definition">
        <template v-for="step in detail.case_definition.steps" :key="step.id">
          <SqlViewer :title="`SQL Query · ${step.id}`" :code="step.sql" />
          <section class="surface">
            <h2 class="surface-title">比较规则 · {{ step.id }}</h2>
            <div class="detail-body detail-kv">
              <span class="key">Comparison Mode</span><span class="mono">{{ step.comparison.mode }}</span>
              <span class="key">Expected</span>
              <pre class="code-block expected-block">{{ JSON.stringify(step.expected, null, 2) }}</pre>
            </div>
          </section>
        </template>
      </template>
      <div v-else-if="detail.report.source_file" class="error-banner">
        当前 Case 文件与运行时记录的源码指纹不一致；为避免展示错误 SQL，已隐藏用例定义。
      </div>

      <section class="surface">
        <h2 class="surface-title">执行结果</h2>
        <div v-for="step in detail.report.steps" :key="step.id" class="step-result">
          <div class="step-head">
            <b>{{ step.id }}</b>
            <StatusTag :status="step.status" />
            <span class="muted">{{ formatDuration(step.duration_ms) }}</span>
          </div>
          <div class="result-grid">
            <div><span>Row Count</span><b>{{ step.row_count ?? '—' }}</b></div>
            <div><span>Result SHA-256</span><b class="digest">{{ step.result_sha256 ?? '—' }}</b></div>
          </div>
          <div v-if="step.columns.length" class="runtime-table-wrap">
            <table class="data-table runtime-table">
              <thead>
                <tr><th>#</th><th>列名</th><th>Driver Type</th><th>Logical Type</th></tr>
              </thead>
              <tbody>
                <tr v-for="(column, index) in step.columns" :key="`${step.id}-${column}-${index}`">
                  <td>{{ index + 1 }}</td>
                  <td>{{ column }}</td>
                  <td>{{ step.column_types[index] ?? '—' }}</td>
                  <td>{{ step.logical_types[index] ?? '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="step.error || step.error_code || step.sqlstate" class="error-detail">
            <b>错误详情</b>
            <div>Error Type：{{ step.error_type ?? '—' }}</div>
            <div>Error Code：{{ step.error_code ?? '—' }} · SQLSTATE：{{ step.sqlstate ?? '—' }}</div>
            <pre>{{ step.error ?? '—' }}</pre>
          </div>
        </div>
        <div v-if="!detail.report.steps.length" class="empty-state">没有 Step 结果</div>
        <div v-if="detail.report.error" class="detail-body error-detail">
          <b>Case 错误</b>
          <pre>{{ detail.report.error }}</pre>
        </div>
      </section>
    </div>
  </template>
  <div v-else-if="!error" class="surface empty-state">{{ loading ? '读取 Case 详情…' : 'Case 不存在' }}</div>
</template>

<style scoped>
.back-row { margin-bottom: 18px; font-size: 12px; }
.case-heading { align-items: center; }
.case-heading h1 { font-size: 23px; }
.case-heading p { margin: 6px 0 0; }
.step-result { padding: 17px 19px; border-bottom: 1px solid var(--line); }
.step-result:last-child { border-bottom: 0; }
.step-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; font-size: 12px; }
.step-head .muted { margin-left: auto; }
.result-grid { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 12px; padding: 10px 0 15px; font-size: 11px; }
.result-grid div { display: grid; gap: 5px; }
.result-grid span { color: var(--muted); }
.result-grid b { font-weight: 500; }
.expected-block { max-height: 190px; }
.error-detail {
  margin: 12px 18px;
  padding: 13px;
  border: 1px solid #f2d0d0;
  border-radius: 5px;
  background: #fff8f8;
  color: #8d3535;
  font-size: 11px;
  line-height: 1.7;
}
.error-detail pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 11px/1.6 ui-monospace, Consolas, monospace;
}
.detail-body.error-detail { margin: 0 18px 18px; }
.digest { overflow-wrap: anywhere; }
</style>
