/**
 * 内部人员（internal）判定 —— 前端**唯一真相源**。
 *
 * 口径对齐后端 `backend/core/permissions.py:44 IsProcurementOrAdmin`：
 *     return user.is_staff or user.role in ('procurement', 'admin')
 *
 * ★ 为什么必须收敛到一处：这条语义曾被复制成 10 份（router 守卫 1 + workspace 页面 9），
 *   2026-10-14 只改了 router 守卫（is_staff → is_staff||role 白名单），页面层 9 处没跟上
 *   ⇒ 非 staff 的 procurement（`is_staff` 注册时不可传 ⇒ 默认 False）过路由层后又被页面层
 *   `router.replace('/')` 踢回首页，"修复"实际无效。
 *   现在 router / 9 个页面 / AppHeader 一律调用本函数，改口径只需改这一处。
 *
 * ★ 安全边界（不要放宽）：非内部人员（普通注册用户、researcher、research_only 等）
 *   必须仍然拿不到工作台/内部台 —— 这是权限边界，不是"体验优化"。
 *
 * 用法：
 *   import { isInternal } from '@/utils/internalAccess'
 *   if (!isInternal(auth)) router.replace('/')            // 页面守卫
 *   <router-link v-if="showInternal">                     // 模板：见 AppHeader.vue
 *
 * @param {{ isStaff?: unknown, role?: unknown } | null | undefined} auth
 *        任何带 isStaff / role 字段的对象 —— Pinia auth store 直接传即可
 *        （store 的 getter 解包后即为布尔/字符串）。也便于纯函数单测。
 * @returns {boolean}
 */
export const INTERNAL_ROLES = Object.freeze(['procurement', 'admin']);

/**
 * 该用户是否属于内部人员（可进 /workspace 与 /ops/* 内部台）。
 * 纯函数：不做路由跳转、不读 DOM、不引 Vue 依赖 ⇒ 可直接 node --test 单测。
 */
export function isInternal(auth) {
  if (!auth) return false;
  // 宽松真值：后端可能序列化成 1 / 'true'，都算 staff。
  return Boolean(auth.isStaff) || INTERNAL_ROLES.includes(auth.role);
}

export default isInternal;