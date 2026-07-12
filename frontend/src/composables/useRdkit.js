/**
 * RDKit.js composable for SMILES → SVG rendering in the browser.
 * Loads RDKit WASM from CDN on first use (lazy).
 */
import { ref } from 'vue'

const rdkitReady = ref(false)
const rdkitLoading = ref(false)
let rdkitInstance = null
let loadPromise = null

const RDKIT_CDN = 'https://unpkg.com/@rdkit/rdkit/dist/RDKit_minimal.js'

/**
 * Load RDKit.js WASM module (once, cached).
 * @returns {Promise<object>} RDKit instance
 */
export function loadRdkit() {
  if (rdkitInstance) return Promise.resolve(rdkitInstance)
  if (loadPromise) return loadPromise

  rdkitLoading.value = true
  loadPromise = new Promise((resolve, reject) => {
    // Check if already loaded
    if (window.initRDKitModule) {
      window.initRDKitModule().then((RDKit) => {
        rdkitInstance = RDKit
        rdkitReady.value = true
        rdkitLoading.value = false
        resolve(RDKit)
      }).catch(reject)
      return
    }

    // Load script from CDN
    const script = document.createElement('script')
    script.src = RDKIT_CDN
    script.async = true
    script.onload = () => {
      if (window.initRDKitModule) {
        window.initRDKitModule().then((RDKit) => {
          rdkitInstance = RDKit
          rdkitReady.value = true
          rdkitLoading.value = false
          resolve(RDKit)
        }).catch(reject)
      } else {
        rdkitLoading.value = false
        reject(new Error('RDKit module loaded but initRDKitModule not found'))
      }
    }
    script.onerror = () => {
      rdkitLoading.value = false
      reject(new Error('Failed to load RDKit.js from CDN'))
    }
    document.head.appendChild(script)
  })

  return loadPromise
}

/**
 * Render SMILES to SVG string.
 * @param {string} smiles - SMILES string
 * @param {object} options - { width, height }
 * @returns {Promise<string>} SVG markup
 */
export async function smilesToSvg(smiles, options = {}) {
  if (!smiles || !smiles.trim()) return ''

  const RDKit = await loadRdkit()
  const { width = 350, height = 250 } = options

  try {
    const mol = RDKit.get_mol(smiles)
    if (!mol) return ''

    const svg = mol.get_svg_with_highlights(JSON.stringify({
      width,
      height,
      bondLineWidth: 1.5,
      addAtomIndices: false,
      addStereoAnnotation: true,
    }))
    mol.delete()
    return svg
  } catch (e) {
    console.warn('[RDKit] Failed to render SMILES:', e.message)
    return ''
  }
}

/**
 * Vue composable for RDKit.
 */
export function useRdkit() {
  return {
    rdkitReady,
    rdkitLoading,
    loadRdkit,
    smilesToSvg,
  }
}

export { rdkitReady, rdkitLoading }
