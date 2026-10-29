import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getProducts, getProduct, getProductDetail } from '@/api/products'

export const useProductsStore = defineStore('products', () => {
  const products = ref([])
  const currentProduct = ref(null)
  const productDetail = ref(null) // V1.2 aggregated detail
  const loading = ref(false)
  const productError = ref(false)      // true 仅表示「后端明确 404」
  const productErrorMsg = ref('')      // 非 404 的失败原因（超时/网络/5xx）
  const total = ref(0)

  async function fetchProducts(params = {}) {
    loading.value = true
    try {
      const result = await getProducts(params)
      products.value = result.data || []
      total.value = result.meta?.pagination?.count || 0
    } catch (err) {
      console.error('Failed to fetch products:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchProduct(id) {
    loading.value = true
    try {
      const result = await getProduct(id)
      currentProduct.value = result.data
    } catch (err) {
      console.error('Failed to fetch product:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchProductDetail(id) {
    loading.value = true
    productError.value = false
    try {
      const result = await getProductDetail(id)
      productDetail.value = result.data
      // Also set currentProduct from the detail for backward compat
      if (result.data?.product) {
        currentProduct.value = result.data.product
      }
      productErrorMsg.value = ''
    } catch (err) {
      console.error('Failed to fetch product detail:', err)
      // ★ 2026-10-29：区分「真的没这个产品」和「网络慢 / 超时」。
      //   之前一律置 productError，导致慢链路超时也被说成「产品不存在」
      //   —— 既误导用户，也误导排查（2026-10-29 就是这样被带偏的）。
      const status = err?.response?.status
      if (status === 404) {
        productError.value = true
        productErrorMsg.value = ''
      } else {
        productError.value = false
        productErrorMsg.value = status
          ? `Server returned ${status}. Please retry in a moment.`
          : (err?.code === 'ECONNABORTED'
              ? 'The request timed out — your connection to our server is slow. Please retry.'
              : 'Network error — could not reach the server. Please retry.')
      }
      // 阶段0：#404 详情失败时置错误态并清残留数据，
      // 避免 SPA 导航后残留上一产品的 currentProduct 导致页面显示错误内容/卡住。
      productError.value = true
      productDetail.value = null
      currentProduct.value = null
    } finally {
      loading.value = false
    }
  }

  function clearCurrent() {
    currentProduct.value = null
    productDetail.value = null
    productError.value = false
  }

  return { products, currentProduct, productDetail, loading, productError, productErrorMsg, total, fetchProducts, fetchProduct, fetchProductDetail, clearCurrent }
})
