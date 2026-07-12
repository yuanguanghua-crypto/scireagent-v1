<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: '' },
  label: { type: String, default: '' },
  dotColor: { type: String, default: '' },
})

// 状态 → 语义圆点色（对齐 DESIGN_STANDARDS.md §6.3 语义色）
const STATUS_DOT = {
  po_received: '#F59E0B',       // 待审/新 → amber
  confirmed: '#3B82F6',         // 已确认 → info
  in_production: '#F59E0B',     // 生产中 → amber
  shipped: '#F59E0B',           // 已发货 → amber
  delivered: '#22C55E',         // 已签收 → green
  invoiced: '#3B82F6',          // 已开票 → info
  paid: '#22C55E',              // 已付款 → green
  completed: '#22C55E',         // 已完成 → green
  cancelled: '#9CA3AF',         // 已取消 → gray
  draft: '#9CA3AF',             // 草稿 → gray
  quote_pending: '#F59E0B',
  quoted: '#D97706',
  quote_accepted: '#22C55E',
  quote_rejected: '#DC2626',
  processing: '#3B82F6',
  // 发票状态
  issued: '#3B82F6',
  overdue: '#DC2626',
  // 发货状态
  pending: '#9CA3AF',
}

const dot = computed(() => props.dotColor || STATUS_DOT[props.status] || '#9CA3AF')
const text = computed(() => props.label || props.status?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || props.status)
</script>

<template>
  <span class="po-badge">
    <span class="po-badge-dot" :style="{ background: dot }"></span>
    {{ text }}
  </span>
</template>
