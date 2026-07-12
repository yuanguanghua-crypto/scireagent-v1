/**
 * 地址管理 store（节点4）
 * @module stores/addresses
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAddresses, createAddress, updateAddress, deleteAddress } from '@/api/addresses'

export const useAddressesStore = defineStore('addresses', () => {
  const addresses = ref([])
  const loading = ref(false)

  async function fetchAddresses(params = {}) {
    loading.value = true
    try {
      const res = await getAddresses(params)
      const payload = res.data || res
      addresses.value = payload.results || payload.data || payload || []
    } catch (err) {
      console.error('[addresses] fetchAddresses failed:', err)
    } finally {
      loading.value = false
    }
  }

  async function addAddress(data) {
    const res = await createAddress(data)
    await fetchAddresses()
    return res
  }

  async function editAddress(id, data) {
    const res = await updateAddress(id, data)
    await fetchAddresses()
    return res
  }

  async function removeAddress(id) {
    const res = await deleteAddress(id)
    await fetchAddresses()
    return res
  }

  return {
    addresses, loading,
    fetchAddresses, addAddress, editAddress, removeAddress,
  }
})
