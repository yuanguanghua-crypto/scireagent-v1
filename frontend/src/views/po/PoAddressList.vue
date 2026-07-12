<script setup>
import { onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useAddressesStore } from '@/stores/addresses'
import { ADDRESS_TYPES } from '@/config/poConstants'

const store = useAddressesStore()
const { addresses, loading } = storeToRefs(store)

const editingId = ref(null)
const showForm = ref(false)
const form = reactive({
  type: 'shipping',
  is_default: false,
  attention: '',
  line1: '',
  line2: '',
  city: '',
  state: '',
  postal_code: '',
  country: 'US',
  phone: '',
})

function resetForm() {
  Object.assign(form, {
    type: 'shipping', is_default: false, attention: '', line1: '', line2: '',
    city: '', state: '', postal_code: '', country: 'US', phone: '',
  })
  editingId.value = null
}

function openNew() {
  resetForm()
  showForm.value = true
}

function openEdit(a) {
  Object.assign(form, {
    type: a.type, is_default: a.is_default, attention: a.attention || '',
    line1: a.line1, line2: a.line2 || '', city: a.city, state: a.state,
    postal_code: a.postal_code, country: a.country, phone: a.phone || '',
  })
  editingId.value = a.id
  showForm.value = true
}

async function save() {
  if (editingId.value) {
    await store.editAddress(editingId.value, { ...form })
  } else {
    await store.addAddress({ ...form })
  }
  showForm.value = false
  resetForm()
}

async function remove(id) {
  if (confirm('Delete this address?')) await store.removeAddress(id)
}

onMounted(() => store.fetchAddresses())
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Address Book</h1>
        <p class="po-page-subtitle">Manage bill-to and ship-to addresses for your organization.</p>
      </div>
      <button class="po-btn po-btn-accent" @click="openNew">+ New Address</button>
    </div>

    <div class="po-callout warn" style="margin-bottom:24px">
      Backend <code>/addresses/</code> CRUD is scheduled for P1. Save actions will surface an error toast until the endpoint ships.
    </div>

    <div class="po-card" v-if="showForm">
      <h2 class="po-section-title">{{ editingId ? 'Edit' : 'New' }} Address</h2>
      <div class="po-form-grid">
        <div class="po-field">
          <label class="po-label">Type</label>
          <select v-model="form.type" class="po-select">
            <option v-for="t in ADDRESS_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </div>
        <div class="po-field">
          <label class="po-label">Country</label>
          <input v-model="form.country" class="po-input" />
        </div>
        <div class="po-field">
          <label class="po-label">Attention</label>
          <input v-model="form.attention" class="po-input" />
        </div>
        <div class="po-field">
          <label class="po-label">Phone</label>
          <input v-model="form.phone" class="po-input" />
        </div>
        <div class="po-field full">
          <label class="po-label">Address Line 1</label>
          <input v-model="form.line1" class="po-input" />
        </div>
        <div class="po-field full">
          <label class="po-label">Address Line 2</label>
          <input v-model="form.line2" class="po-input" />
        </div>
        <div class="po-field"><label class="po-label">City</label><input v-model="form.city" class="po-input" /></div>
        <div class="po-field"><label class="po-label">State</label><input v-model="form.state" class="po-input" /></div>
        <div class="po-field"><label class="po-label">Postal Code</label><input v-model="form.postal_code" class="po-input" /></div>
        <div class="po-field" style="align-self:end">
          <label class="po-row" style="gap:6px;font-size:14px;color:var(--color-text-secondary)">
            <input type="checkbox" v-model="form.is_default" /> Default for type
          </label>
        </div>
      </div>
      <div class="po-row" style="margin-top:16px">
        <button class="po-btn po-btn-primary" @click="save">Save</button>
        <button class="po-btn po-btn-outline" @click="showForm = false">Cancel</button>
      </div>
    </div>

    <div class="po-card">
      <table class="po-table" v-if="addresses.length">
        <thead>
          <tr><th>Type</th><th>Attention</th><th>Address</th><th>Country</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="a in addresses" :key="a.id">
            <td><span class="po-tag">{{ a.type }}</span> <span v-if="a.is_default" class="po-muted">· default</span></td>
            <td>{{ a.attention || '—' }}</td>
            <td>{{ a.line1 }}<span v-if="a.line2">, {{ a.line2 }}</span>, {{ a.city }} {{ a.state }} {{ a.postal_code }}</td>
            <td>{{ a.country }}</td>
            <td>
              <div class="po-row">
                <button class="po-btn po-btn-outline po-btn-sm" @click="openEdit(a)">Edit</button>
                <button class="po-btn po-btn-danger po-btn-sm" @click="remove(a.id)">Delete</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="po-empty">Loading…</div>
      <div v-else class="po-empty">No addresses yet.</div>
    </div>
  </div>
</template>
