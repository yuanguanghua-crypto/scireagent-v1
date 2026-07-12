<script setup>
const props = defineProps({
  currentPage: {
    type: Number,
    required: true,
  },
  pageSize: {
    type: Number,
    default: 20,
  },
  total: {
    type: Number,
    required: true,
  },
  pageSizes: {
    type: Array,
    default: () => [10, 20, 50, 100],
  },
  layout: {
    type: String,
    default: 'total, sizes, prev, pager, next, jumper',
  },
  background: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['update:currentPage', 'update:pageSize', 'change'])

function handleCurrentChange(page) {
  emit('update:currentPage', page)
  emit('change', { page, pageSize: props.pageSize })
}

function handleSizeChange(size) {
  emit('update:pageSize', size)
  emit('change', { page: 1, pageSize: size })
}
</script>

<template>
  <div class="data-pagination">
    <el-pagination
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      :page-sizes="pageSizes"
      :layout="layout"
      :background="background"
      @current-change="handleCurrentChange"
      @size-change="handleSizeChange"
    />
  </div>
</template>

<style scoped>
.data-pagination {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}
/* 覆盖 Element Plus 页码按钮尺寸 */
.data-pagination :deep(.el-pagination button),
.data-pagination :deep(.el-pager li) {
  min-width: 20px;
  height: 20px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 20px;
}
.data-pagination :deep(.el-pager li.active) {
  background: var(--color-emerald-600);
  color: #fff;
  border-color: var(--color-emerald-600);
}
.data-pagination :deep(.el-pager li:not(.active)) {
  background: transparent;
  color: var(--color-gray-500);
}
.data-pagination :deep(.el-pagination .el-pagination__editor) {
  border-radius: 4px;
}
</style>