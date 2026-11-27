export { default as AppButton } from './AppButton.vue'
export { default as AppDialog } from './AppDialog.vue'
export { default as AppToast, toast } from './AppToast.js'
export { default as ConfirmHost } from './ConfirmHost.vue'

// 保留已有——不要动其他已有 common 组件
export { default as DataPagination } from './DataPagination.vue'
export { default as EmptyState } from './EmptyState.vue'
export { default as ErrorBanner } from './ErrorBanner.vue'
export { default as ErrorState } from './ErrorState.vue'
export { default as LoadingSpinner } from './LoadingSpinner.vue'
export { default as AppInput } from './AppInput.vue'
export { default as AppSelect } from './AppSelect.vue'
// ★ 2026-11-27（A-249 收尾）：日期输入统一实现，替代 `<input type="date">`
//   （后者分段输入会把手打的 YYYY-MM-DD 吃成脏值，见组件头注）
export { default as IsoDateInput } from './IsoDateInput.vue'
export { default as StatusBadge } from './StatusBadge.vue'
