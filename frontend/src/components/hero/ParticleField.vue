<script setup>
/**
 * ParticleField — 粒子网络 canvas（hero 背景层）
 *
 * 透明背景铺满父级（.hero），继承深色渐变。鼠标交互（桌面）。
 * prefers-reduced-motion → 静态一帧。document.hidden → 暂停。
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useParticleField } from '@/composables/useParticleField'
import { PERF } from '@/config/particleField.config'

const wrapEl = ref(null)
const canvasEl = ref(null)
const field = useParticleField()

let rafId = null
let last = 0
let running = false
let ctx = null
let dpr = 1
let ro = null
const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function setupCanvas() {
  const w = wrapEl.value.clientWidth
  const h = wrapEl.value.clientHeight
  if (!w || !h) return null
  dpr = Math.min(window.devicePixelRatio || 1, PERF.dprMax)
  canvasEl.value.width = Math.floor(w * dpr)
  canvasEl.value.height = Math.floor(h * dpr)
  canvasEl.value.style.width = w + 'px'
  canvasEl.value.style.height = h + 'px'
  ctx = canvasEl.value.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return { w, h }
}

function frame(t) {
  if (!running) return
  const dt = last ? Math.min((t - last) / 1000, PERF.dtClamp) : 0
  last = t
  field.update(dt)
  if (ctx) {
    ctx.clearRect(0, 0, canvasEl.value.width / dpr, canvasEl.value.height / dpr)
    field.draw(ctx)
  }
  rafId = requestAnimationFrame(frame)
}

function start() {
  if (running) return
  running = true
  last = 0
  rafId = requestAnimationFrame(frame)
}
function stop() {
  running = false
  if (rafId != null) cancelAnimationFrame(rafId)
  rafId = null
}

function onMouseMove(e) {
  if (!canvasEl.value || reduced) return
  const rect = canvasEl.value.getBoundingClientRect()
  field.setMouse(e.clientX - rect.left, e.clientY - rect.top, true)
}
function onMouseLeave() {
  field.setMouse(0, 0, false)
}

function onVisibility() {
  if (document.hidden) stop()
  else if (!reduced) start()
}

onMounted(() => {
  const size = setupCanvas()
  if (!size) return
  field.build(size.w, size.h)

  if (reduced) {
    if (ctx) {
      ctx.clearRect(0, 0, size.w, size.h)
      field.drawStatic(ctx)
    }
    return
  }

  start()

  ro = new ResizeObserver(() => {
    const s = setupCanvas()
    if (s) field.resize(s.w, s.h)
  })
  ro.observe(wrapEl.value)

  window.addEventListener('mousemove', onMouseMove, { passive: true })
  wrapEl.value.addEventListener('mouseleave', onMouseLeave)
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => {
  stop()
  ro?.disconnect()
  window.removeEventListener('mousemove', onMouseMove)
  wrapEl.value?.removeEventListener('mouseleave', onMouseLeave)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<template>
  <div ref="wrapEl" class="particle-field">
    <canvas ref="canvasEl" class="particle-field__canvas" aria-hidden="true" />
  </div>
</template>

<style scoped>
.particle-field {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background: transparent;   /* 继承 .hero 深色渐变，内生于背景 */
  pointer-events: none;      /* 不挡 CTA 交互 */
  z-index: 1;
}
.particle-field__canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}
</style>
