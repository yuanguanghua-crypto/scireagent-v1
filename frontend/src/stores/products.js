import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getProducts, getProduct } from '@/api/products'

export const useProductsStore = defineStore('products', () => {
  const products = ref([])
  const currentProduct = ref(null)
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

  function clearCurrent() {
    currentProduct.value = null
  }

  return { products, currentProduct, loading, total, fetchProducts, fetchProduct, clearCurrent }
})
