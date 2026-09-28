<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  tone?: 'default' | 'pass' | 'fail' | 'error' | 'timeout'
}>()
</script>

<template>
  <div class="metric">
    <span class="metric-label">{{ label }}</span>
    <strong class="metric-value" :class="tone && tone !== 'default' ? `text-${tone}` : undefined">{{ value }}</strong>
  </div>
</template>
