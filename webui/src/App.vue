<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'
const route = useRoute()
const section = computed(() => route.path === '/' ? '概览' : route.path.endsWith('/scope') ? '测试空间' : route.path.startsWith('/tests') ? '测试目标' : route.path.startsWith('/jobs') ? '测试任务' : route.path.startsWith('/runs') ? '运行记录' : route.path.startsWith('/coverage') ? '覆盖情况' : route.path.startsWith('/candidates') ? '候选用例' : '运行环境')
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <RouterLink class="brand" to="/" aria-label="XG DB Test 首页"><span class="brand-mark">XG</span><span><b>XG DB Test</b><small>Query QA</small></span></RouterLink>
      <nav aria-label="主导航">
        <RouterLink to="/tests" :class="{ active: route.path.startsWith('/tests') }"><span class="nav-glyph">✦</span>测试目标</RouterLink>
        <RouterLink to="/jobs" :class="{ active: route.path.startsWith('/jobs') }"><span class="nav-glyph">▷</span>测试任务</RouterLink>
        <RouterLink to="/" :class="{ active: route.path === '/' }"><span class="nav-glyph">◫</span>仪表盘</RouterLink>
        <RouterLink to="/runs" :class="{ active: route.path.startsWith('/runs') }"><span class="nav-glyph">≡</span>运行记录</RouterLink>
        <RouterLink to="/runtime" :class="{ active: route.path === '/runtime' }"><span class="nav-glyph">◉</span>运行环境</RouterLink>
        <RouterLink to="/coverage" :class="{ active: route.path === '/coverage' }"><span class="nav-glyph">▦</span>覆盖情况</RouterLink>
        <RouterLink to="/candidates" :class="{ active: route.path.startsWith('/candidates') }"><span class="nav-glyph">◇</span>候选用例</RouterLink>
      </nav>
      <div class="sidebar-foot"><span class="live-dot"></span>只读结果视图</div>
    </aside>
    <main class="main-shell">
      <header class="topbar"><span>{{ section }}</span><span class="topbar-note">XG 数据库测试 · Query MVP</span></header>
      <div class="page-content"><RouterView /></div>
    </main>
  </div>
</template>

<style scoped>
@media (max-width: 600px) {
  .sidebar nav { grid-template-columns: repeat(7, minmax(0, 1fr)); }
}
</style>
