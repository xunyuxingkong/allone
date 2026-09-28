<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { QueryCaseReport } from '../types'
import StatusTag from './StatusTag.vue'
import { formatDuration } from '../utils'

const props = defineProps<{
  runId: string
  cases: QueryCaseReport[]
  loading?: boolean
  emptyText?: string
  sortable?: boolean
  sortDir?: 'asc' | 'desc' | null
}>()

const emit = defineEmits<{
  sortDuration: []
}>()
</script>

<template>
  <div class="table-scroll">
    <table class="data-table">
      <thead>
        <tr>
          <th>Case ID</th>
          <th>Feature</th>
          <th>状态</th>
          <th>
            <button
              v-if="sortable"
              type="button"
              class="sort-button"
              @click="emit('sortDuration')"
            >
              耗时
              <span class="sort-indicator">{{ sortDir === 'asc' ? '↑' : sortDir === 'desc' ? '↓' : '↕' }}</span>
            </button>
            <template v-else>耗时</template>
          </th>
          <th>Failure Type</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in cases" :key="item.case_id">
          <td>
            <RouterLink class="link mono" :to="`/runs/${props.runId}/cases/${item.case_id}`">{{ item.case_id }}</RouterLink>
            <div class="case-title">{{ item.title }}</div>
          </td>
          <td>{{ item.feature ?? '—' }}</td>
          <td><StatusTag :status="item.status" /></td>
          <td>{{ formatDuration(item.duration_ms) }}</td>
          <td class="mono">{{ item.failure_type ?? '—' }}</td>
        </tr>
      </tbody>
    </table>
    <div v-if="!cases.length" class="empty-state">{{ loading ? '读取中…' : (emptyText ?? '没有匹配的 Case') }}</div>
  </div>
</template>

<style scoped>
.case-title { margin-top: 4px; color: #8793a3; font-size: 10px; }
.sort-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 700;
  letter-spacing: .04em;
  cursor: pointer;
}
.sort-indicator { color: #95a0af; font-size: 10px; }
</style>
