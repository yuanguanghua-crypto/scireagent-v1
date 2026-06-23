<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { StandaloneStructServiceProvider } from 'ketcher-standalone'
import { Ketcher } from 'ketcher-core'
import { Editor } from 'ketcher-react'

const props = defineProps({
  smiles: { type: String, default: '' },
})

const emit = defineEmits(['update:smiles'])

const showEditor = ref(false)
const ketcherRef = ref(null)

const structServiceProvider = new StandaloneStructServiceProvider()

let ketcherInstance = null

function toggleEditor() {
  showEditor.value = !showEditor.value
}

function handleInit(ketcher) {
  ketcherInstance = ketcher
  if (props.smiles?.trim()) {
    setTimeout(() => {
      ketcher.setMolecule(props.smiles.trim())
    }, 300)
  }
}

async function importSmiles() {
  if (!ketcherInstance || !props.smiles?.trim()) return
  await ketcherInstance.setMolecule(props.smiles.trim())
}

async function exportSmiles() {
  if (!ketcherInstance) return
  try {
    const result = await ketcherInstance.getSmiles()
    if (result) {
      emit('update:smiles', result)
    }
  } catch (e) {
    console.warn('Ketcher export failed:', e)
  }
}

watch(() => props.smiles, (newVal) => {
  if (ketcherInstance && newVal?.trim()) {
    ketcherInstance.setMolecule(newVal.trim())
  }
})
</script>

<template>
  <div class="ketcher-wrapper">
    <div class="ketcher-toolbar">
      <button type="button" class="btn btn-ghost btn-sm" @click="toggleEditor">
        {{ showEditor ? '✕ Close Editor' : '✏️ Open Structure Editor' }}
      </button>
      <button
        v-if="showEditor"
        type="button"
        class="btn btn-ghost btn-sm"
        @click="importSmiles"
      >
        📥 Load SMILES from Form
      </button>
      <button
        v-if="showEditor"
        type="button"
        class="btn btn-primary btn-sm"
        @click="exportSmiles"
      >
        📤 Export to Form
      </button>
    </div>
    <div v-if="showEditor" class="ketcher-editor-frame">
      <Editor
        ref="ketcherRef"
        :staticResourcesUrl="'/ketcher/'"
        :structServiceProvider="structServiceProvider"
        @onInit="handleInit"
      />
    </div>
  </div>
</template>

<style scoped>
.ketcher-wrapper { margin-top: 8px; }
.ketcher-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.ketcher-editor-frame { height: 520px; border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
</style>
