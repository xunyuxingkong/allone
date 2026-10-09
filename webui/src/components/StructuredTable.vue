<script setup lang="ts">
import { computed } from 'vue'
import ResultRowsTable from './ResultRowsTable.vue'

const props = defineProps<{ value: unknown }>()
const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const record = computed(() => isRecord(props.value) ? props.value : null)
const resultRows = computed(() => record.value && Array.isArray(record.value.rows) && record.value.rows.every(Array.isArray) ? record.value.rows as unknown[][] : null)
const array = computed(() => Array.isArray(props.value) ? props.value : null)
const objectRows = computed(() => array.value?.length && array.value.every(isRecord) ? array.value as Record<string, unknown>[] : null)
const keys = computed(() => [...new Set(objectRows.value?.flatMap(row => Object.keys(row)) ?? [])])
const entries = computed(() => Object.entries(record.value ?? {}).filter(([key]) => !resultRows.value || !['rows', 'columns', 'column_types'].includes(key)))
const columns = computed(() => Array.isArray(record.value?.columns) ? record.value.columns : [])
const columnTypes = computed(() => Array.isArray(record.value?.column_types) ? record.value.column_types : [])
const scalar = computed(() => props.value === null ? 'NULL' : props.value === undefined ? '—' : props.value === '' ? "''（空字符串）" : String(props.value))
</script>

<template>
  <div v-if="record" class="structured-data">
    <ResultRowsTable v-if="resultRows" :rows="resultRows" :columns="columns" :column-types="columnTypes" />
    <div v-if="entries.length" class="structured-scroll"><table class="data-table field-table"><thead><tr><th scope="col">字段</th><th scope="col">值 / 明细</th></tr></thead><tbody><tr v-for="[key, item] in entries" :key="key"><th scope="row">{{ key }}</th><td><StructuredTable :value="item" /></td></tr></tbody></table></div>
    <span v-else-if="!resultRows" class="muted">无字段</span>
  </div>
  <div v-else-if="array" class="structured-scroll">
    <table v-if="objectRows && keys.length" class="data-table object-table"><thead><tr><th scope="col">#</th><th v-for="key in keys" :key="key" scope="col">{{ key }}</th></tr></thead><tbody><tr v-for="(row, index) in objectRows" :key="index"><th scope="row">{{ index + 1 }}</th><td v-for="key in keys" :key="key"><StructuredTable :value="row[key]" /></td></tr></tbody></table>
    <table v-else-if="array.length" class="data-table field-table"><thead><tr><th scope="col">#</th><th scope="col">值 / 明细</th></tr></thead><tbody><tr v-for="(item, index) in array" :key="index"><th scope="row">{{ index + 1 }}</th><td><StructuredTable :value="item" /></td></tr></tbody></table>
    <span v-else class="muted">空列表（0 项）</span>
  </div>
  <span v-else class="scalar-value">{{ scalar }}</span>
</template>

<style scoped>
.structured-data, .structured-scroll { min-width: 0; max-width: 100%; }
.structured-scroll { overflow-x: auto; }
.field-table { min-width: 0; }
.field-table tbody th { background: transparent; white-space: normal; overflow-wrap: anywhere; width: 150px; vertical-align: top; }
.field-table td { min-width: 150px; vertical-align: top; }
.object-table { min-width: max-content; }
.scalar-value { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
