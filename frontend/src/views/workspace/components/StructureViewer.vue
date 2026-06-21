<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  smiles: { type: String, default: '' },
})

const imgUrl = ref('')
const error = ref('')

async function renderSmiles(smiles) {
  if (!smiles || !smiles.trim()) {
    imgUrl.value = ''
    error.value = ''
    return
  }
  try {
    const encoded = encodeURIComponent(smiles.trim())
    imgUrl.value = `https://cactus.nci.nih.gov/chemical/structure/${encoded}/image`
    error.value = ''
  } catch {
    imgUrl.value = ''
    error.value = 'Invalid SMILES'
  }
}

watch(() => props.smiles, renderSmiles, { immediate: true })
</script>

<template>
  <div class="structure-viewer">
    <img v-if="imgUrl" :src="imgUrl" alt="Structure" class="structure-img" @error="error = 'Preview unavailable'" />
    <p v-else-if="error" class="structure-error">{{ error }}</p>
    <p v-else class="structure-placeholder">Structure preview<br><small>Enter SMILES to preview</small></p>
  </div>
</template>

<style scoped>
.structure-viewer {
  width: 250px; min-height: 250px; border: 1px solid var(--color-border);
  border-radius: 12px; display: flex; align-items: center; justify-content: center;
  background: #fff; flex-shrink: 0; overflow: hidden;
}
.structure-img { max-width: 100%; max-height: 100%; object-fit: contain; }
.structure-placeholder { text-align: center; color: var(--color-text-secondary); font-size: 14px; }
.structure-placeholder small { font-size: 11px; display: block; margin-top: 4px; }
.structure-error { color: #dc3545; font-size: 13px; }
</style>
