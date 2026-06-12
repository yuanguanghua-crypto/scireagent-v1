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
</style>