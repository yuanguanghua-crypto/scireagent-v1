<script setup>
/**
 * EntityListToolbar —— 知识实体治理页的统一列表工具栏（S4 / A-066 + A-014）。
 *
 * 起因（实测，不是偏好）：Goals / Applications / Methods / Protocols 四页
 * `el-input` 命中数为 **0**、`el-pagination` 命中数为 **0**，
 * `page_size` 硬编码 200/200/200/500 ⇒ 2.8 万条应用只能靠肉眼翻第一页找。
 *
 * 三个控件：
 *  - 搜索框：四页后端都支持 `?search=`（Methods/Apps/Goals 走 DRF SearchFilter，
 *            Protocols 在 `get_queryset` 里自实现并**额外命中 facet 标签**）。
 *  - Show drafts 复选框：默认**不勾**（保留 2026-10-26 方案 B 默认口径）。
 *  - 状态下拉：**只在勾了 Show drafts 后出现** —— 不勾时全库只剩公开态一种，
 *            再给个「选公开态之外的状态」的下拉只会让人以为能筛出草稿却没反应。
 */
const props = defineProps({
  search: { type: String, default: '' },
  showDrafts: { type: Boolean, default: false },
  status: { type: String, default: '' },
  /** [{ value, label }]；首项约定为「全部状态」（value='') */
  statusOptions: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Search…' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:search', 'update:showDrafts', 'update:status', 'submit'])

function onInput(v) {
  emit('update:search', v)
}
function onDrafts(v) {
  emit('update:showDrafts', v)
  // 关掉开关时顺带清空状态筛选 —— 否则残留的 status=archived 会和
  // publicStatus 语义打架（关着却按归档筛，界面显示空表）。
  if (!v) emit('update:status', '')
  emit('submit')
}
function onStatus(v) {
  emit('update:status', v)
  emit('submit')
}
</script>

<template>
  <div class="entity-toolbar" data-testid="entity-list-toolbar">
    <div class="toolbar-row">
      <el-input
        :model-value="search"
        :placeholder="placeholder"
        prefix-icon="Search"
        clearable
        class="toolbar-search"
        @update:model-value="onInput"
        @keyup.enter="emit('submit')"
        @clear="emit('submit')"
      />
      <button class="btn btn-ghost btn-sm" :disabled="loading" @click="emit('submit')">Search</button>

      <label class="drafts-toggle">
        <input
          type="checkbox"
          :checked="showDrafts"
          data-testid="show-drafts-toggle"
          @change="onDrafts($event.target.checked)"
        />
        <span>Show drafts &amp; archived</span>
      </label>

      <el-select
        v-if="showDrafts"
        :model-value="status"
        class="toolbar-status"
        size="default"
        placeholder="All statuses"
        @update:model-value="onStatus"
      >
        <el-option
          v-for="o in statusOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
    </div>
  </div>
</template>

<style scoped>
.entity-toolbar {
  margin-bottom: 12px;
}
.toolbar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.toolbar-search {
  max-width: 320px;
  min-width: 200px;
}
.toolbar-status {
  width: 190px;
}
.drafts-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
.drafts-toggle input {
  cursor: pointer;
  accent-color: var(--color-primary);
}
</style>
