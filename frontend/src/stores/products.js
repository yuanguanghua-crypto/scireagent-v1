import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getProducts, getProduct, getProductDetail } from '@/api/products'

export const useProductsStore = defineStore('products', () => {
  const products = ref([])
  const currentProduct = ref(null)
  const productDetail = ref(null) // V1.2 aggregated detail
  const loading = ref(false)
  const productError = ref(false)
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
    } catch (err) {
      console.error('Failed to fetch product detail:', err)
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

  return { products, currentProduct, productDetail, loading, productError, total, fetchProducts, fetchProduct, fetchProductDetail, clearCurrent }
})
