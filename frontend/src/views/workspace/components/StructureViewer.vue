<script setup>
import { ref, watch } from 'vue'
import { renderStructure } from '@/api/aiTools'

const props = defineProps({
  smiles: { type: String, default: '' },
  pubchemCid: { type: [Number, String], default: null },
})

const svgContent = ref('')
const canonicalSmiles = ref('')
const error = ref('')
const loading = ref(false)

function buildPubChemUrl(smiles) {
  if (!smiles || !smiles.trim()) return null
  try {
    const encoded = smiles.trim()
      .replace(/#/g, '%23')
      .replace(/\[/g, '%5B')
      .replace(/\]/g, '%5D')
      .replace(/@/g, '%40')
      .replace(/\//g, '%2F')
      .replace(/\\/g, '%5C')
      .replace(/=/g, '%3D')
      .replace(/\(/g, '%28')
      .replace(/\)/g, '%29')
    return `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/${encoded}/PNG?image_size=300x300`
  } catch {
    return null
  }
}

function buildCactusUrl(smiles) {
  if (!smiles || !smiles.trim()) return null
  try {
    const encoded = encodeURIComponent(smiles.trim())
    return `https://cactus.nci.nih.gov/chemical/structure/${encoded}/image`
  } catch {
    return null
  }
}

async function renderSmiles(smiles) {
  svgContent.value = ''
  canonicalSmiles.value = ''
  error.value = ''

  if (!smiles || !smiles.trim()) {
    return
  }

  // 策略 0: RDKit 本地渲染（优先级最高 — 出版级 SVG，离线零网络依赖）
  try {
    const resp = await renderStructure(smiles)
    if (resp?.data?.svg) {
      svgContent.value = resp.data.svg
      if (resp.data.canonical_smiles) {
        canonicalSmiles.value = resp.data.canonical_smiles
      }
      return
    }
  } catch { /* fall through */ }

  // 策略 1: PubChem CID
  if (props.pubchemCid) {
    const cidUrl = `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/CID/${props.pubchemCid}/PNG?image_size=300x300`
    if (await testImgUrl(cidUrl)) {
      svgContent.value = `<img src="${cidUrl}" alt="Structure" style="max-width:100%;max-height:100%;object-fit:contain" />`
      return
    }
  }

  // 策略 2: PubChem SMILES
  const pubchemUrl = buildPubChemUrl(smiles)
  if (pubchemUrl && await testImgUrl(pubchemUrl)) {
    svgContent.value = `<img src="${pubchemUrl}" alt="Structure" style="max-width:100%;max-height:100%;object-fit:contain" />`
    return
  }

  // 策略 3: Cactus Fallback
  const cactusUrl = buildCactusUrl(smiles)
  if (cactusUrl) {
    svgContent.value = `<img src="${cactusUrl}" alt="Structure" style="max-width:100%;max-height:100%;object-fit:contain" />`
  }
}

async function testImgUrl(url) {
  try {
    const resp = await fetch(url, { method: 'HEAD' })
    return resp.ok && resp.headers.get('content-type')?.includes('image')
  } catch {
    return false
  }
}

watch(() => [props.smiles, props.pubchemCid], () => renderSmiles(props.smiles), { immediate: true })
</script>

<template>
  <div class="structure-viewer">
    <div v-if="svgContent" class="structure-svg" v-html="svgContent" />
    <p v-else-if="error" class="structure-error">{{ error }}</p>
    <p v-else class="structure-placeholder">Structure preview<br><small>Enter SMILES to preview</small></p>
    <div v-if="canonicalSmiles" class="canonical-smiles" :title="canonicalSmiles">
      <span style="font-size:10px;color:var(--color-text-secondary)">Canonical SMILES:</span>
      <code style="font-size:9px;word-break:break-all;color:var(--color-text-secondary);display:block;margin-top:2px">{{ canonicalSmiles }}</code>
    </div>
  </div>
</template>

<style scoped>
.structure-viewer {
  width: 250px; min-height: 250px; border: 1px solid var(--color-border);
  border-radius: 12px; display: flex; flex-direction: column; align-items: center;
  justify-content: center; background: #fff; flex-shrink: 0; overflow: hidden;
  position: relative;
}
.structure-svg { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.structure-svg :deep(svg) { max-width: 100%; max-height: 100%; }
.structure-svg :deep(img) { max-width: 100%; max-height: 100%; object-fit: contain; }
.structure-placeholder { text-align: center; color: var(--color-text-secondary); font-size: 14px; }
.structure-placeholder small { font-size: 11px; display: block; margin-top: 4px; }
.structure-error { color: #dc3545; font-size: 13px; }
.canonical-smiles {
  position: absolute; bottom: 0; left: 0; right: 0; padding: 4px 6px;
  background: rgba(248,250,252,0.92); border-top: 1px solid var(--color-border);
}
</style>
