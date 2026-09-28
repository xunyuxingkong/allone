<script setup lang="ts">
defineProps<{
  title?: string
  code: string
}>()
</script>

<template>
  <section class="surface">
    <h2 v-if="title" class="surface-title">{{ title }}</h2>
    <pre class="code-block">{{ code }}</pre>
  </section>
</template>
