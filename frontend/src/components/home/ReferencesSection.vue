<script setup>
/**
 * ReferencesSection — 首页「Recent Publications」。
 *
 * ★ 2026-10-30 修（用户报「标题点不了」）：
 *   原来只有 `DOI: xxx` 那一行是 `<a>`，标题是 `<h4>` 纯文本。而首页展示的
 *   那 5 条恰好 DOI 全空（后端排序 bug 把 year=NULL 的行顶到最前，见 site_views
 *   的注释），于是整条记录**没有任何可点的地方**。
 *
 *   现在：标题本身就是链接，DOI 优先、url 兜底；两者都没有时才降级为纯文本。
 *   同时 DOI 行改为不可点的元信息（避免与标题指向同一地址、出现两个跳转点）。
 *   期刊名也从主题色改为次要色 —— 它一直没有链接，用链接色会让人误点。
 */
defineProps({
  references: { type: Array, default: () => [] },
})

const DOI_PREFIX = /^https?:\/\/(dx\.)?doi\.org\//i

/** 返回可跳转地址；DOI 优先，其次 url，都没有返回 null。 */
function linkOf(ref) {
  const doi = (ref.doi || '').trim().replace(DOI_PREFIX, '')
  if (doi) return `https://doi.org/${doi}`
  const url = (ref.url || '').trim()
  return url || null
}
</script>

<template>
  <section v-if="references.length" class="section" aria-label="Recent Publications">
    <div class="section-header">
      <h2 class="section-title">Recent Publications</h2>
    </div>
    <div class="refs-list">
      <div v-for="ref in references" :key="ref.id" class="ref-item">
        <a
          v-if="linkOf(ref)"
          class="ref-title ref-title-link"
          :href="linkOf(ref)"
          target="_blank"
          rel="noopener noreferrer"
        >{{ ref.title }}</a>
        <h4 v-else class="ref-title">{{ ref.title }}</h4>

        <div class="ref-meta">
          <span v-if="ref.journal" class="ref-journal">{{ ref.journal }}</span>
          <span v-if="ref.year" class="ref-year">{{ ref.year }}</span>
          <span v-if="ref.doi" class="ref-doi">DOI: {{ ref.doi }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.section { margin-bottom: 32px; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}
.refs-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ref-item {
  padding: 14px 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: border-color 0.15s;
}
.ref-item:hover { border-color: var(--color-primary); }

.ref-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 6px;
  line-height: 1.4;
  text-decoration: none;
}
.ref-title-link { cursor: pointer; }
.ref-title-link:hover {
  color: var(--color-primary);
  text-decoration: underline;
}

.ref-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 12px;
}
/* 期刊名原本用主题色，看着像链接却点不动 —— 改为次要色 */
.ref-journal {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}
.ref-year {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.ref-doi {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  opacity: 0.8;
  word-break: break-all;
}
</style>
