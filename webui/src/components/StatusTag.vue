<script setup lang="ts">
import type { RunStatus } from '../types'
defineProps<{ status: RunStatus | 'PENDING' | 'RUNNING' | 'SKIPPED' }>()
const labels: Record<string, string> = { PASS: '通过', FAIL: '失败', ERROR: '错误', TIMEOUT: '超时', INFRA_RECOVERED: '已恢复', PENDING: '待运行', RUNNING: '运行中', SKIPPED: '跳过' }
</script>

<template><span class="status-tag" :class="`status-${status.toLowerCase()}`"><i></i>{{ labels[status] ?? status }}</span></template>
