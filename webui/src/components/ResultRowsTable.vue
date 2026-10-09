<script setup lang="ts">
import { computed } from 'vue'
import StructuredTable from './StructuredTable.vue'

const props = withDefaults(defineProps<{ rows: unknown[][]; columns?: unknown[]; columnTypes?: unknown[]; offset?: number }>(), { columns: () => [], columnTypes: () => [], offset: 0 })
const width = computed(() => Math.max(props.columns.length, props.columnTypes.length, ...props.rows.map(row => row.length), 0))
</script>

<template>
  <div class="result-scroll">
    <table v-if="width" class="data-table result-table">
      <thead><tr><th scope="col">行号</th><th v-for="index in width" :key="index" scope="col">{{ columns[index - 1] ?? `第 ${index} 列` }}<span v-if="columnTypes[index - 1] != null" class="column-type">{{ columnTypes[index - 1] }}</span></th></tr></thead>
      <tbody><tr v-for="(row, index) in rows" :key="index"><th scope="row">{{ offset + index + 1 }}</th><td v-for="column in width" :key="column"><StructuredTable :value="row[column - 1]" /></td></tr></tbody>
    </table>
    <p v-if="!rows.length" class="muted empty-result">结果为 0 行</p>
  </div>
</template>

<style scoped>
.result-scroll { overflow-x: auto; max-width: 100%; }
.result-table { min-width: max-content; }
.result-table tbody th { background: transparent; }
.column-type { display: block; margin-top: 4px; font-weight: normal; }
.empty-result { padding: 10px; }
</style>
