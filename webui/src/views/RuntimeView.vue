<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getContract, getRuntimeProfile, getTypeSupport } from '../api/runtime'
import type { RuntimeProfileView } from '../api/runtime'
import TypeSupportTable from '../components/TypeSupportTable.vue'
import { shortId } from '../utils'

const profile = ref<RuntimeProfileView | null>(null)
const contract = ref<{ contract_version: string; contract_set_id: string; descriptor_version: string } | null>(null)
const types = ref<{ available: boolean; items: Record<string, string | null>[] } | null>(null)
const error = ref('')

onMounted(async () => {
  const [profileResult, contractResult, typeResult] = await Promise.allSettled([
    getRuntimeProfile(),
    getContract(),
    getTypeSupport(),
  ])
  if (profileResult.status === 'fulfilled') profile.value = profileResult.value
  else error.value = '尚未配置 Runtime Profile；请将已验证的 Profile 路径设为 XGTEST_RUNTIME_PROFILE。'
  if (contractResult.status === 'fulfilled') contract.value = contractResult.value
  if (typeResult.status === 'fulfilled') types.value = typeResult.value
})

function value(record: Record<string, unknown> | undefined, key: string) {
  const result = record?.[key]
  return result == null ? '—' : String(result)
}
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>运行环境</h1>
      <p>查看 Runtime Profile、Contract 与 Driver 类型支持证据。</p>
    </div>
  </div>
  <div v-if="error" class="error-banner">{{ error }}</div>

  <section class="surface runtime-overview">
    <h2 class="surface-title">运行环境概览</h2>
    <div class="detail-body detail-kv">
      <span class="key">Database Product</span><span>{{ value(profile?.target, 'database_product') }}</span>
      <span class="key">Database Version</span><span>{{ value(profile?.target, 'database_version') }}</span>
      <span class="key">Driver Name</span><span>{{ value(profile?.driver, 'module') }}</span>
      <span class="key">Driver Version</span><span>{{ JSON.stringify(profile?.driver.version ?? '—') }}</span>
      <span class="key">Python Version</span><span>{{ JSON.stringify(profile?.driver.python_version ?? '—') }}</span>
      <span class="key">OS / Arch</span><span>{{ value(profile?.target, 'os') }} / {{ value(profile?.target, 'arch') }}</span>
      <span class="key">Runtime Profile ID</span><span class="mono">{{ profile?.sql_runtime_profile_id ?? '—' }}</span>
      <span class="key">Contract Set ID</span><span class="mono">{{ contract?.contract_set_id ?? profile?.contract_set_id ?? '—' }}</span>
      <span class="key">Evidence Hash</span><span class="digest">{{ profile?.evidence_sha256 ?? '—' }}</span>
      <span class="key">Contract Version</span><span class="mono">{{ contract?.contract_version ?? '—' }}</span>
    </div>
  </section>

  <section class="surface">
    <h2 class="surface-title">数据库类型支持矩阵</h2>
    <TypeSupportTable
      :items="types?.items ?? []"
      :empty-text="types?.available === false ? '尚未配置 Runtime Profile' : 'Profile 中没有类型映射证据'"
    />
  </section>

  <div v-if="profile" class="runtime-foot">
    Profile {{ shortId(profile.sql_runtime_profile_id) }} · Contract {{ shortId(contract?.contract_set_id ?? profile.contract_set_id) }}
  </div>
</template>

<style scoped>
.runtime-overview { margin-bottom: 16px; }
.runtime-foot { padding: 14px 2px; color: #8995a5; font: 10px ui-monospace, Consolas, monospace; }
.detail-body { padding: 19px; }
.digest { overflow-wrap: anywhere; }
</style>
