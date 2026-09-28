<script setup lang="ts">
defineProps<{
  items: Record<string, string | null>[]
  emptyText?: string
}>()

function fidelity(value: unknown) {
  return ({ EXACT: '精确保真', LOSSY: '有损', AMBIGUOUS: '语义不明', UNKNOWN: '未知' } as Record<string, string>)[String(value)] ?? '—'
}
</script>

<template>
  <div class="runtime-table-wrap">
    <table class="data-table runtime-table">
      <thead>
        <tr>
          <th>Driver Type</th>
          <th>Logical Type</th>
          <th>Fidelity</th>
          <th>Canonical</th>
          <th>Support</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="String(item.driver_type)">
          <td class="mono">{{ item.driver_type }}</td>
          <td>{{ item.framework_logical_type ?? item.logical_type ?? '—' }}</td>
          <td>{{ fidelity(item.mapping_fidelity) }}</td>
          <td>{{ item.canonical_encoding ?? '—' }}</td>
          <td>
            <span class="support-state" :class="item.support_status === 'SUPPORTED' ? 'supported' : 'unsupported'">
              <i></i>{{ item.support_status === 'SUPPORTED' ? '支持' : '不支持' }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!items.length" class="empty-state">{{ emptyText ?? '暂无类型映射证据' }}</div>
  </div>
</template>

<style scoped>
.support-state { display: inline-flex; align-items: center; gap: 7px; font-size: 11px; color: #6c7788; }
.support-state i { width: 7px; height: 7px; border-radius: 50%; background: #a8b1bd; }
.support-state.supported i { background: #198653; }
.support-state.unsupported i { background: #c64343; }
</style>
