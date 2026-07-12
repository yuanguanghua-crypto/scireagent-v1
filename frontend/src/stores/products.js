import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getProducts, getProduct, getProductDetail } from '@/api/products'

export const useProductsStore = defineStore('products', () => {
  const products = ref([])
  const currentProduct = ref(null)
  const productDetail = ref(null) // V1.2 aggregated detail
  const loading = ref(false)
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
    try {
      const result = await getProductDetail(id)
      productDetail.value = result.data
      // Also set currentProduct from the detail for backward compat
      if (result.data?.product) {
        currentProduct.value = result.data.product
      }
    } catch (err) {
      console.error('Failed to fetch product detail:', err)
    } finally {
      loading.value = false
    }
  }

  function clearCurrent() {
    currentProduct.value = null
    productDetail.value = null
  }

  return { products, currentProduct, productDetail, loading, total, fetchProducts, fetchProduct, fetchProductDetail, clearCurrent }
})
