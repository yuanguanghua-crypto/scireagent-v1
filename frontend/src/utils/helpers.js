/**
 * Format date to locale string
 */
export function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text, length = 100) {
  if (!text) return ''
  return text.length > length ? text.slice(0, length) + '...' : text
}

/**
 * Get status badge type for Element Plus
 */
export function getStatusType(status) {
  const map = {
    active: 'success',
    draft: 'info',
    deprecated: 'warning',
    archived: 'danger',
    published: 'success',
    superseded: 'warning',
  }
  return map[status] || 'info'
}

/**
 * Format currency
 */
export function formatCurrency(amount, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amount)
}