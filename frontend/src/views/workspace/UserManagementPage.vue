<script setup>
/**
 * 用户与角色 —— 运营台，替代 Django admin 的日常操作。
 *
 * 允许做的（后端白名单，前端只暴露这些）：
 *   改 role / 启停账号 / 手动验证邮箱 / 触发密码重置邮件
 *
 * 刻意没有的：
 *   ✗ 直接改密码 —— 密码只能由本人通过邮件链接设置（管理员能设密码=能冒充用户）
 *   ✗ 改 is_staff / is_superuser —— 提权，必须走 Django admin
 *   ✗ 删除用户 —— 有订单/线索关联
 *   ✗ 改自己 —— 后端会 400（防自锁），前端也把按钮禁掉
 */
import { onMounted, ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  getUsers, patchUser, verifyUserEmail, sendUserPasswordReset,
} from '@/api/system'
import { extractErrorMessage } from '@/utils/http'

const auth = useAuthStore()

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const flash = ref('')
const busyId = ref(null)

const search = ref('')
const roleFilter = ref('')
const verifiedFilter = ref('')

const ROLES = ['researcher', 'procurement', 'editor', 'admin']

const myId = computed(() => auth.user?.id ?? null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page_size: 200 }
    if (search.value.trim()) params.search = search.value.trim()
    if (roleFilter.value) params.role = roleFilter.value
    if (verifiedFilter.value) params.email_verified = verifiedFilter.value
    const res = await getUsers(params)
    const payload = res.data ?? res
    rows.value = Array.isArray(payload) ? payload : (payload.results || [])
    total.value = res.meta?.pagination?.count ?? rows.value.length
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load users.")
  } finally {
    loading.value = false
  }
}

function say(msg) {
  flash.value = msg
  window.setTimeout(() => { flash.value = '' }, 3000)
}

function isSelf(r) {
  return myId.value != null && r.id === myId.value
}

async function changeRole(r, ev) {
  const next = ev.target.value
  if (next === r.role) return
  busyId.value = r.id
  error.value = ''
  try {
    await patchUser(r.id, { role: next })
    say(`#${r.id} ${r.username} 的角色已改为 ${next}`)
    await load()
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't change role.")
    ev.target.value = r.role        // 失败回滚下拉显示
  } finally {
    busyId.value = null
  }
}

async function toggleActive(r) {
  const next = !r.is_active
  if (!next && !window.confirm(`停用 ${r.username}？停用后该账号所有登录凭证立即失效。`)) return
  busyId.value = r.id
  error.value = ''
  try {
    await patchUser(r.id, { is_active: next })
    say(`${r.username} 已${next ? '启用' : '停用'}`)
    await load()
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't update account status.")
  } finally {
    busyId.value = null
  }
}

async function doVerify(r) {
  if (!window.confirm(`把 ${r.username} 标记为邮箱已验证？\n\n这会绕过邮箱验证 —— 只在邮件通道故障或客户紧急时使用。`)) return
  busyId.value = r.id
  try {
    const res = await verifyUserEmail(r.id)
    const d = res.data ?? res
    say(d.already_verified ? `${r.username} 本来就是已验证状态` : `${r.username} 已标记为已验证`)
    await load()
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't verify this account.")
  } finally {
    busyId.value = null
  }
}

async function doSendReset(r) {
  if (!window.confirm(`向 ${r.email} 发送密码重置链接？`)) return
  busyId.value = r.id
  try {
    const res = await sendUserPasswordReset(r.id)
    const d = res.data ?? res
    say(d.queued
      ? `重置邮件已入队，发往 ${r.email}`
      : `邮件未能入队，请人工转达重置链接（控制台已记录）`)
    await load()
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't send reset email.")
  } finally {
    busyId.value = null
  }
}

function fmtDate(v) {
  if (!v) return '—'
  try { return new Date(v).toLocaleDateString() } catch { return String(v) }
}

onMounted(async () => {
  // 刷新页面后 store 里可能只有 token、没有 user ⇒ isSelf 永远 false，
  // 自己的按钮不会被禁用（虽然后端仍会 400）。先补一次。
  if (!auth.user) {
    try { await auth.fetchUser() } catch { /* 失败不阻塞列表加载 */ }
  }
  await load()
})
</script>

<template>
  <div class="um-page">
    <div class="um-header">
      <div>
        <h1 class="um-title">Users &amp; Roles</h1>
        <p class="um-sub">
          {{ total }} account(s) · 只能改角色/启停/验证邮箱；密码由本人通过邮件设置
        </p>
      </div>
      <button class="um-btn" :disabled="loading" @click="load">
        {{ loading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    <div v-if="error" class="um-alert um-alert--err">{{ error }}</div>
    <div v-if="flash" class="um-alert um-alert--ok">{{ flash }}</div>

    <div class="um-filters">
      <input
        v-model.trim="search"
        class="um-input"
        placeholder="Search username, email, organization…"
        @keyup.enter="load"
      />
      <select v-model="roleFilter" class="um-input um-input--sm" @change="load">
        <option value="">All roles</option>
        <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
      </select>
      <select v-model="verifiedFilter" class="um-input um-input--sm" @change="load">
        <option value="">Any email state</option>
        <option value="true">Verified</option>
        <option value="false">Unverified</option>
      </select>
      <button class="um-btn um-btn--primary" :disabled="loading" @click="load">Apply</button>
    </div>

    <div class="um-table-wrap">
      <table class="um-table">
        <thead>
          <tr>
            <th>Username</th><th>Email</th><th>Role</th>
            <th>Status</th><th>Email</th><th>Joined</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id" :class="{ 'is-self': isSelf(r) }">
            <td>
              <span class="um-mono">{{ r.username }}</span>
              <span v-if="isSelf(r)" class="um-tag">you</span>
            </td>
            <td class="um-email">{{ r.email || '—' }}</td>
            <td>
              <select
                class="um-input um-input--xs"
                :value="r.role"
                :disabled="isSelf(r) || busyId === r.id"
                @change="changeRole(r, $event)"
              >
                <option v-for="role in ROLES" :key="role" :value="role">{{ role }}</option>
              </select>
            </td>
            <td>
              <span class="um-badge" :class="r.is_active ? 'ok' : 'off'">
                {{ r.is_active ? 'active' : 'disabled' }}
              </span>
            </td>
            <td>
              <span class="um-badge" :class="r.email_verified ? 'ok' : 'warn'">
                {{ r.email_verified ? 'verified' : 'unverified' }}
              </span>
            </td>
            <td class="um-dim">{{ fmtDate(r.date_joined) }}</td>
            <td class="um-actions">
              <button
                class="um-btn um-btn--xs"
                :disabled="isSelf(r) || busyId === r.id"
                @click="toggleActive(r)"
              >{{ r.is_active ? 'Disable' : 'Enable' }}</button>
              <button
                v-if="!r.email_verified"
                class="um-btn um-btn--xs"
                :disabled="busyId === r.id"
                @click="doVerify(r)"
              >Verify email</button>
              <button
                class="um-btn um-btn--xs"
                :disabled="isSelf(r) || !r.is_active || busyId === r.id"
                @click="doSendReset(r)"
              >Send reset</button>
            </td>
          </tr>
          <tr v-if="!rows.length && !loading">
            <td colspan="7" class="um-empty">No accounts match.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="um-foot">
      自己的角色/启停按钮是禁用状态 —— 后端也会拒绝，防止把自己锁在门外。
      最后一个管理员不能降级或停用。
    </p>
  </div>
</template>

<style scoped>
.um-page { padding: 24px; max-width: 1240px; }
.um-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.um-title { font-size: 20px; font-weight: 700; margin: 0 0 4px; color: var(--color-text, #111827); }
.um-sub { font-size: 13px; color: var(--color-text-tertiary, #6b7280); margin: 0; }

.um-alert { padding: 9px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 12px; }
.um-alert--err { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }
.um-alert--ok { background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d; }

.um-filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.um-input {
  padding: 7px 10px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  font-size: 13px; background: var(--color-bg, #fff); color: var(--color-text, #111827);
  min-width: 200px;
}
.um-input--sm { min-width: 140px; }
.um-input--xs { min-width: 108px; padding: 4px 6px; font-size: 12px; }

.um-btn {
  padding: 7px 12px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  background: var(--color-bg, #fff); color: var(--color-text, #111827);
  font-size: 13px; cursor: pointer; white-space: nowrap;
}
.um-btn--primary { background: var(--color-primary, #2563eb); border-color: var(--color-primary, #2563eb); color: #fff; }
.um-btn--xs { padding: 4px 8px; font-size: 12px; }
.um-btn:disabled { opacity: .45; cursor: not-allowed; }

.um-table-wrap { overflow-x: auto; border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px; }
.um-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.um-table th {
  text-align: left; font-size: 12px; font-weight: 600; color: var(--color-text-tertiary, #6b7280);
  padding: 9px 12px; border-bottom: 1px solid var(--color-border, #e5e7eb); white-space: nowrap;
}
.um-table td { padding: 8px 12px; border-bottom: 1px solid var(--color-border, #f3f4f6); vertical-align: middle; }
.um-table tr.is-self { background: #f8fafc; }
.um-mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.um-email { max-width: 240px; overflow-wrap: anywhere; }
.um-dim { color: var(--color-text-tertiary, #6b7280); white-space: nowrap; }
.um-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.um-empty { text-align: center; padding: 24px; color: var(--color-text-tertiary, #6b7280); }

.um-tag {
  margin-left: 6px; font-size: 10px; padding: 1px 6px; border-radius: 8px;
  background: #e0e7ff; color: #3730a3; font-weight: 600;
}
.um-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.um-badge.ok { background: #dcfce7; color: #15803d; }
.um-badge.warn { background: #fef3c7; color: #92400e; }
.um-badge.off { background: #f3f4f6; color: #6b7280; }

.um-foot { font-size: 12px; color: var(--color-text-tertiary, #6b7280); margin-top: 12px; line-height: 1.6; }

@media (max-width: 720px) { .um-page { padding: 16px; } }
</style>
