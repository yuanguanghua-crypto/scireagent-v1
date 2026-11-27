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
  getUsers, patchUser, verifyUserEmail, sendUserPasswordReset, createUser,
} from '@/api/system'
import { extractErrorMessage } from '@/utils/http'
// ★ 2026-11-26（A-030）：管理员建号（不含密码，密码由本人邮件设置）
import { useConfirm } from '@/composables/useConfirm'

const auth = useAuthStore()
// ★ 2026-11-18（S4）：原生 window.confirm 换成页内确认框 —— 文案可控、
// 危险动作有视觉等级、且 e2e 能断言「点取消后确实没写入」。
const { ask } = useConfirm()

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const flash = ref('')
const busyId = ref(null)

const search = ref('')
const roleFilter = ref('')
const verifiedFilter = ref('')
// ★ 2026-11-26（A-233）：账号启停筛选。后端 `OpsUserListView.get_queryset()`
// 早就支持 `is_active` 参数（与 email_verified 同一循环），只是前端一直没给入口 ——
// 想清点"还有哪些停用账号"只能翻页肉眼找。
const statusFilter = ref('')

const ROLES = ['researcher', 'procurement', 'editor', 'admin']

const myId = computed(() => auth.user?.id ?? null)

// ★ 2026-11-26（A-030）：建号表单。**没有 password 字段** —— 见 api/system.js 的说明
const showCreate = ref(false)
const creating = ref(false)
const createForm = ref({ username: '', email: '', role: 'researcher' })
const createError = ref('')

function openCreate() {
  createForm.value = { username: '', email: '', role: 'researcher' }
  createError.value = ''
  showCreate.value = true
}

async function submitCreate() {
  const { username, email, role } = createForm.value
  if (!username.trim() || !email.trim()) {
    createError.value = '用户名与邮箱都必填。'
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const res = await createUser({
      username: username.trim(), email: email.trim(), role,
    })
    const d = res.data || res
    showCreate.value = false
    say(
      d.password_reset_queued
        ? `已建号 ${d.username}，设置密码的邮件已发出。`
        : `已建号 ${d.username}，但重置邮件未发出 — 请手动点该行的「Send reset」。`,
    )
    await load()
  } catch (e) {
    createError.value = extractErrorMessage(e?.response?.data ?? e, 'Could not create this user.')
  } finally {
    creating.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page_size: 200 }
    if (search.value.trim()) params.search = search.value.trim()
    if (roleFilter.value) params.role = roleFilter.value
    if (verifiedFilter.value) params.email_verified = verifiedFilter.value
    if (statusFilter.value) params.is_active = statusFilter.value
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
    // ★ 2026-11-26（A-022）：先把本行的值改成已提交的新 role，再重新拉列表。
    //   此前只靠 `await load()` 回填 —— 回填是异步的，而在 disabled 窗口里
    //   下拉显示的是 DOM 自身状态，于是用户看到"灰掉 + 还是旧值"，
    //   会以为没生效又去点一次。乐观更新让"显示的"与"已提交的"从这一刻起一致，
    //   后续 load() 只是拿服务端真值覆盖（若服务端拒绝，catch 会回滚下拉）。
    r.role = next
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
  if (!next) {
    const ok = await ask({
      title: '停用账号',
      message: `停用 ${r.username}？\n\n停用后该账号所有登录凭证立即失效，该用户将无法再登录。`,
      confirmText: '停用',
      danger: true,
    })
    if (!ok) return
  }
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
  const ok = await ask({
    title: '标记邮箱已验证',
    message: `把 ${r.username} 标记为邮箱已验证？\n\n这会绕过邮箱验证流程 —— 只在邮件通道故障或客户紧急时使用。`,
    confirmText: '标记已验证',
    danger: true,
  })
  if (!ok) return
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
  const ok = await ask({
    title: '发送密码重置链接',
    message: `向 ${r.email} 发送密码重置链接？`,
    confirmText: '发送',
  })
  if (!ok) return
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
          <!-- ★ 2026-11-26（A-012）：加载中不能显示 "0 record(s)" ——
               那是"还没取到"被当成"结果是空"，用户会以为筛选没匹配到。
               与 RfqDesk 的 subtitle 用同一写法（loading 时只说 Loading…）。 -->
          {{ loading ? 'Loading…' : `${total} account(s) · 只能改角色/启停/验证邮箱；密码由本人通过邮件设置` }}
        </p>
      </div>
      <div class="um-header-actions">
        <!-- ★ 2026-11-26（A-030）：建号入口。此前只能让对方自助注册再改角色 -->
        <button class="um-btn um-btn--primary" @click="openCreate">+ New User</button>
        <button class="um-btn" :disabled="loading" @click="load">
          {{ loading ? 'Refreshing…' : 'Refresh' }}
        </button>
      </div>
    </div>

    <!-- ★ 2026-11-26（A-030）：建号对话框。刻意**没有密码输入框** ——
         后端 set_unusable_password() + 发重置邮件，密码由本人设。 -->
    <div v-if="showCreate" class="um-modal-overlay" @click.self="showCreate = false">
      <div class="um-modal">
        <h3>New User</h3>
        <p class="um-modal-hint">
          建号后系统会给该邮箱发一封「设置密码」邮件。
          <strong>管理员无法设定密码</strong> —— 这是为了让操作日志里的"谁做的"始终可信。
        </p>
        <label class="um-field">
          <span>Username</span>
          <input v-model="createForm.username" class="um-input" autocomplete="off" />
        </label>
        <label class="um-field">
          <span>Email</span>
          <input v-model="createForm.email" class="um-input" type="email" autocomplete="off" />
        </label>
        <label class="um-field">
          <span>Role</span>
          <select v-model="createForm.role" class="um-input">
            <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
          </select>
        </label>
        <p v-if="createError" class="um-alert um-alert--err">{{ createError }}</p>
        <div class="um-modal-actions">
          <button class="um-btn" :disabled="creating" @click="showCreate = false">Cancel</button>
          <button class="um-btn um-btn--primary" :disabled="creating" @click="submitCreate">
            {{ creating ? 'Creating…' : 'Create & send reset link' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ★ 2026-11-26（A-030）：建号对话框。刻意**没有密码输入框** ——
         后端 set_unusable_password() + 发重置邮件，密码由本人设。 -->
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
        <!-- ★ 2026-11-26（A-092）：选 admin 时后端按「能进后台」判定
             （role='admin' ∪ is_staff ∪ is_superuser），所以会带出 role 显示为
             researcher 但实际是 staff/superuser 的账号。选项文案把这层说清楚。 -->
        <option v-for="r in ROLES" :key="r" :value="r">
          {{ r === 'admin' ? 'admin (+ staff/superuser)' : r }}
        </option>
      </select>
      <select v-model="verifiedFilter" class="um-input um-input--sm" @change="load">
        <option value="">Any email state</option>
        <option value="true">Verified</option>
        <option value="false">Unverified</option>
      </select>
      <!-- A-233：账号启停筛选（后端 is_active 早已支持，缺的一直是这个入口） -->
      <select v-model="statusFilter" class="um-input um-input--sm" @change="load">
        <option value="">Any status</option>
        <option value="true">Active</option>
        <option value="false">Disabled</option>
      </select>
      <button class="um-btn um-btn--primary" :disabled="loading" @click="load">Apply</button>
    </div>

    <div class="um-table-wrap">
      <table class="um-table">
        <thead>
          <tr>
            <th>Username</th><th>Email</th><th>Role</th>
            <!-- ★ 2026-11-26（A-008）：这一列是「邮箱验证状态」，此前误写成第二个 Email，
                 和左边第 2 列的邮箱地址同名，读表头根本分不出哪个是地址、哪个是状态。 -->
            <th>Status</th><th>Email status</th><th>Joined</th><th>Actions</th>
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
              <!-- ★ 2026-11-26（A-092）：「能不能进后台」有三条独立通道
                   （role='admin' / is_staff / is_superuser），而本页下拉只能改 role。
                   把另外两条如实标出来，这样「筛 admin 为什么会出来一个 researcher」
                   在界面上自己就说得清，不用去翻代码。 -->
              <span v-if="r.is_superuser" class="um-badge super" title="is_superuser=True">superuser</span>
              <span v-else-if="r.is_staff" class="um-badge staff" title="is_staff=True">staff</span>
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
.um-header-actions { display: flex; gap: 8px; }
/* ★ 2026-11-26（A-030）：建号对话框 */
.um-modal-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.um-modal {
  background: var(--color-surface); border-radius: var(--radius-md, 8px);
  padding: 20px 22px; width: 100%; max-width: 420px;
  max-height: 85vh; overflow-y: auto;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.22);
}
.um-modal h3 { margin: 0 0 8px; font-size: 17px; }
.um-modal-hint { font-size: 12px; color: var(--color-text-secondary); margin: 0 0 14px; line-height: 1.5; }
.um-field { display: block; margin-bottom: 12px; }
.um-field > span { display: block; font-size: 12px; font-weight: 600; color: var(--color-text-tertiary); margin-bottom: 4px; }
.um-modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
.um-badge.off { background: #f3f4f6; color: #6b7280; }
/* A-092：后台权限标记（与 role 是两回事，必须视觉上可区分） */
.um-badge.staff { background: #e0e7ff; color: #3730a3; margin-left: 4px; }
.um-badge.super { background: #ede9fe; color: #5b21b6; margin-left: 4px; }

.um-foot { font-size: 12px; color: var(--color-text-tertiary, #6b7280); margin-top: 12px; line-height: 1.6; }

@media (max-width: 720px) { .um-page { padding: 16px; } }
</style>
