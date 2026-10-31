<script setup>
/**
 * WishlistPage — 收藏夹（单收藏夹模式）
 *
 * 设计决策：本页只操作「当前用户的第一个收藏夹」。
 *   加载 → GET /wishlist/；结果为空且已登录 ⇒ 自动 POST 创建 { name: 'My Wishlist' }。
 *   因为后端 `product_ids` 是**整体替换**语义，移除/清空都必须「读-改-写」。
 *   匿名访问：后端 GET 仍返回 200 + 空 results（不是 401），因此必须显式给出登录提示，
 *   不能把「空列表」直接渲染成空态。
 */
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import ProductCard from '@/components/cards/ProductCard.vue'
import { AppButton, LoadingSpinner, toast } from '@/components/common'
import { getWishlists, createWishlist, updateWishlist } from '@/api/wishlist'

const authStore = useAuthStore()

const loading = ref(true)
const errorText = ref('')
const wishlist = ref(null)
const busy = ref(false)

/** 拦截器对 {success,data,meta} 返回整个信封——统一在这里取 data */
function unwrap(res) {
  return res && res.data !== undefined ? res.data : res
}
/** 列表响应可能是分页信封 { results } 或裸数组 */
function toList(res) {
  const payload = unwrap(res)
  if (Array.isArray(payload)) return payload
  return Array.isArray(payload?.results) ? payload.results : []
}

const products = computed(() => wishlist.value?.products || [])
const count = computed(() => products.value.length)
/** 当前收藏的产品 id（PATCH 前的「读」） */
const productIds = computed(() => products.value.map((p) => p.id))

async function loadWishlist() {
  if (!authStore.isAuthenticated) {
    loading.value = false
    return
  }
  loading.value = true
  errorText.value = ''
  try {
    const list = toList(await getWishlists())
    if (list.length > 0) {
      wishlist.value = list[0]
    } else {
      // 单收藏夹模式：没有就自动建一个
      wishlist.value = unwrap(await createWishlist({ name: 'My Wishlist' }))
      toast.success('收藏夹已创建')
    }
  } catch (e) {
    errorText.value = '收藏夹加载失败'
    console.error('Failed to load wishlist', e)
  } finally {
    loading.value = false
  }
}

/** PATCH 整体替换，并用返回的序列化结果刷新本地状态（含 products） */
async function replaceProducts(ids) {
  const res = await updateWishlist(wishlist.value.id, { product_ids: ids })
  wishlist.value = unwrap(res)
}

async function removeProduct(product) {
  if (busy.value) return
  busy.value = true
  try {
    // 读-改-写：product_ids 是整体替换，不能只传被删的那个 id
    await replaceProducts(productIds.value.filter((id) => id !== product.id))
    toast.success('已从收藏夹移除')
  } catch {
    // http 拦截器已弹出后端真实错误（如 400 归档产品），此处只保证按钮状态不变
  } finally {
    busy.value = false
  }
}

async function clearAll() {
  if (busy.value || count.value === 0) return
  busy.value = true
  try {
    await replaceProducts([])
    toast.success('收藏夹已清空')
  } catch {
    /* 错误提示已由拦截器给出 */
  } finally {
    busy.value = false
  }
}

onMounted(loadWishlist)
</script>

<template>
  <div class="wl-page">
    <div class="wl-header">
      <div class="wl-header-left">
        <h1 class="wl-title">My Wishlist</h1>
        <span v-if="authStore.isAuthenticated && count > 0" class="wl-count">{{ count }} items</span>
      </div>
      <AppButton
        v-if="authStore.isAuthenticated && count > 0"
        variant="ghost"
        size="sm"
        :disabled="busy"
        @click="clearAll"
      >
        清空收藏
      </AppButton>
    </div>

    <!-- 匿名：明确提示 + 登录入口（后端匿名 GET 返回空列表，不能显示成「空收藏夹」） -->
    <div v-if="!authStore.isAuthenticated" class="wl-notice">
      <h2 class="wl-notice-title">请先登录后使用收藏夹</h2>
      <p class="wl-notice-sub">登录后即可收藏产品，并在任何设备上查看你的收藏夹。</p>
      <div class="wl-notice-actions">
        <AppButton variant="primary" size="sm" to="/login?redirect=/wishlist">Sign In</AppButton>
        <AppButton variant="outline" size="sm" to="/register">Register</AppButton>
      </div>
    </div>

    <!-- 加载中 -->
    <LoadingSpinner v-else-if="loading" text="Loading wishlist..." />

    <!-- 加载失败 -->
    <div v-else-if="errorText" class="wl-notice">
      <h2 class="wl-notice-title">{{ errorText }}</h2>
      <div class="wl-notice-actions">
        <AppButton variant="outline" size="sm" @click="loadWishlist">重试</AppButton>
      </div>
    </div>

    <!-- 空态 -->
    <div v-else-if="count === 0" class="wl-empty">
      <p class="wl-empty-title">还没有收藏任何产品</p>
      <p class="wl-empty-sub">在产品详情页点击「收藏」，就能把产品存到这里。</p>
      <router-link to="/products" class="wl-empty-link">去逛逛产品目录 →</router-link>
    </div>

    <!-- 产品网格 -->
    <div v-else class="wl-grid">
      <div v-for="p in products" :key="p.id" class="wl-item">
        <ProductCard :product="p" />
        <button
          type="button"
          class="wl-remove"
          :disabled="busy"
          :aria-label="`移除 ${p.name}`"
          @click.stop="removeProduct(p)"
        >
          移除
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wl-page {
  max-width: var(--content-max-width, 1200px);
  margin: 0 auto;
  padding: 0 32px 48px;
}

.wl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.wl-header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.wl-title {
  font-size: 26px;
  font-weight: 800;
  color: var(--color-text);
  margin: 0;
  font-family: var(--font-display);
}
.wl-count {
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* ── Notice / error ── */
.wl-notice {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: var(--radius-lg, 12px);
  padding: 40px 32px;
  text-align: center;
}
.wl-notice-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 8px;
}
.wl-notice-sub {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 20px;
}
.wl-notice-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}

/* ── Empty ── */
.wl-empty {
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg, 12px);
  padding: 56px 32px;
  text-align: center;
  background: var(--color-surface);
}
.wl-empty-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 8px;
}
.wl-empty-sub {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 18px;
}
.wl-empty-link {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
  text-decoration: none;
}
.wl-empty-link:hover { text-decoration: underline; }

/* ── Grid ── */
.wl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.wl-item {
  position: relative;
  min-width: 0;
}
.wl-remove {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 2;
  height: 26px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
  transition: all 0.15s;
}
.wl-remove:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
}
.wl-remove:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 768px) {
  .wl-page { padding: 0 20px 40px; }
  .wl-grid { grid-template-columns: 1fr; }
}
</style>
