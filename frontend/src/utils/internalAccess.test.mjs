// 内部人员判定 · 单元 + 收敛守卫测试
//
// 背景：2026-10-14 路由层（router/index.js requiresAdmin）已把口径改为
//   「内部人员 = is_staff 或 role∈(procurement, admin)」，但 9 个 workspace 页面组件
//   各自留了一份只认 isStaff 的旧守卫 ⇒ 非 staff 的 procurement 被页面层 router.replace('/') 踢回首页，
//   路由层的修复实际无效。本测试锁定两件事：
//   (A) isInternal() 的纯函数行为（含安全边界：普通注册用户仍须被拒）；
//   (B) 收敛不变量：9 个页面组件不得再出现裸 `!auth.isStaff` 守卫，且必须引用共享判定。
//
// 口径来源（唯一真相源在后端）：backend/core/permissions.py:44 IsProcurementOrAdmin
//   return user.is_staff or user.role in ('procurement', 'admin')
// 前端任何地方都不得再自行拼这条语义，一律调 utils/internalAccess.js。

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { isInternal, INTERNAL_ROLES } from './internalAccess.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(__dirname, '..');
const WS = path.join(SRC, 'views', 'workspace');

// AdminLayout + 8 个实体页。VerifiedPage.vue 从来没有页面级守卫（只靠路由层），不在此列。
const GUARDED_PAGES = [
  'AdminLayout.vue',
  'AppsPage.vue',
  'DashboardPage.vue',
  'GoalsPage.vue',
  'MethodsPage.vue',
  'ProductEditPage.vue',
  'ProductsPage.vue',
  'ProtocolsPage.vue',
  'ReferencesPage.vue',
];

// ---------------------------------------------------------------------------
// (A) 纯函数行为 —— 核心回归：本次缺陷本体
// ---------------------------------------------------------------------------
test('回归：isStaff=false + role=procurement ⇒ 内部人员（本次缺陷本体）', () => {
  assert.equal(isInternal({ isStaff: false, role: 'procurement' }), true);
});

test('isStaff=true 任意角色 ⇒ 内部人员', () => {
  assert.equal(isInternal({ isStaff: true, role: 'researcher' }), true);
  assert.equal(isInternal({ isStaff: true, role: '' }), true);
});

test('role=admin 且非 staff ⇒ 内部人员', () => {
  assert.equal(isInternal({ isStaff: false, role: 'admin' }), true);
});

test('★ 安全边界：非内部人员必须仍被拒（不得放宽成「任何登录用户都能进」）', () => {
  for (const role of ['researcher', 'research_only', 'customer', '', null, undefined]) {
    assert.equal(
      isInternal({ isStaff: false, role }),
      false,
      `role=${JSON.stringify(role)} 不得被当作内部人员`,
    );
  }
});

test('空/缺失 auth 对象不得抛异常（守卫在 setup 顶层同步调用）', () => {
  assert.equal(isInternal(null), false);
  assert.equal(isInternal(undefined), false);
  assert.equal(isInternal({}), false);
});

test('isStaff 用宽松真值判定（后端可能给 1/true/"true"）', () => {
  assert.equal(isInternal({ isStaff: 1, role: 'researcher' }), true);
  assert.equal(isInternal({ isStaff: 'true', role: 'researcher' }), true);
});

test('INTERNAL_ROLES 与后端 permissions.py 口径一致', () => {
  assert.deepEqual([...INTERNAL_ROLES].sort(), ['admin', 'procurement']);
});

// ---------------------------------------------------------------------------
// (B) 收敛不变量 —— 防「口径分裂」复发
// ---------------------------------------------------------------------------
test('9 个 workspace 页面组件已无裸 !auth.isStaff 守卫', () => {
  const offenders = [];
  for (const f of GUARDED_PAGES) {
    const src = fs.readFileSync(path.join(WS, f), 'utf8');
    if (/!\s*auth\.isStaff/.test(src) || /!\s*authStore\.isStaff/.test(src)) {
      offenders.push(f);
    }
  }
  assert.deepEqual(offenders, [], `这些页面仍在用只认 isStaff 的旧守卫：${offenders.join(', ')}`);
});

test('9 个 workspace 页面组件的守卫统一走 isInternal()', () => {
  const offenders = [];
  for (const f of GUARDED_PAGES) {
    const src = fs.readFileSync(path.join(WS, f), 'utf8');
    if (!/isInternal\(/.test(src)) offenders.push(f);
  }
  assert.deepEqual(offenders, [], `这些页面未引用共享判定：${offenders.join(', ')}`);
});

test('AppHeader 的内部台入口按 isInternal() 放行（procurement 需看到入口）', () => {
  const src = fs.readFileSync(path.join(SRC, 'components', 'layout', 'AppHeader.vue'), 'utf8');
  assert.ok(/isInternal\(/.test(src), 'AppHeader.vue 未引用共享判定 isInternal()');
  assert.ok(
    !/v-if="authStore\.isStaff"/.test(src),
    'AppHeader.vue 仍用 v-if="authStore.isStaff" ⇒ procurement 看不到 Workspace / Order Management 入口',
  );
});

test('路由层 requiresAdmin 守卫同样走 isInternal()（不再内联拼语义）', () => {
  const src = fs.readFileSync(path.join(SRC, 'router', 'index.js'), 'utf8');
  assert.ok(/isInternal\(/.test(src), 'router/index.js 未引用共享判定 isInternal()');
  assert.ok(
    !/auth\.isStaff\s*\|\|\s*\['procurement',\s*'admin'\]/.test(src),
    'router/index.js 仍内联拼 role 白名单 ⇒ 与 isInternal 构成两份口径',
  );
});

test('PublicNav 的 Workspace 入口也按 isInternal() 收口（普通用户不该点了又被弹回）', () => {
  const src = fs.readFileSync(path.join(SRC, 'components', 'layout', 'PublicNav.vue'), 'utf8');
  assert.ok(/isInternal\(/.test(src), 'PublicNav.vue 未引用共享判定 isInternal()');
  assert.ok(
    !/<router-link to="\/workspace" class="nav-user-item"/.test(src),
    'PublicNav.vue 的 Workspace 入口仍对所有登录用户可见',
  );
});

test('DashboardPage 不再把 token 是否存在打进 console', () => {
  const src = fs.readFileSync(path.join(WS, 'DashboardPage.vue'), 'utf8');
  assert.ok(
    !/console\.log\([^)]*localStorage\.getItem\(['"]token['"]\)/.test(src),
    'DashboardPage.vue 仍有打印 token 存在性的 debug log',
  );
});