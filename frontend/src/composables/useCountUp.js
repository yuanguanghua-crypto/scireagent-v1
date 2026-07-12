/**
 * useCountUp — 数字递增动画（IntersectionObserver 触发，一次性）
 *
 * 用于 StatsBar：进入视口时数字从 0 递增到目标值，错峰启动。
 * 尊重 prefers-reduced-motion（直接显示终值，不动画）。
 */
import { onBeforeUnmount } from 'vue'

const prefersReduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export function useCountUp(duration = 1400, stagger = 120) {
  let observer = null
  const rafIds = new Set()
  let started = false

  function animate(setter, target, delay) {
    if (prefersReduced) { setter(target); return }
    const startT = performance.now() + delay
    const tick = (now) => {
      if (now < startT) { rafIds.add(requestAnimationFrame(tick)); return }
      const p = Math.min(1, (now - startT) / duration)
      const eased = 1 - Math.pow(1 - p, 3) // outCubic
      setter(Math.round(target * eased))
      if (p < 1) rafIds.add(requestAnimationFrame(tick))
    }
    rafIds.add(requestAnimationFrame(tick))
  }

  /** items: [{ setter, value }, ...]；rootEl 进入视口时启动 */
  function watch(rootEl, items) {
    if (!rootEl || prefersReduced) {
      items.forEach(it => it.setter(it.value))
      return
    }
    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !started) {
        started = true
        items.forEach((it, i) => animate(it.setter, it.value, i * stagger))
        observer?.disconnect()
      }
    }, { threshold: 0.3 })
    observer.observe(rootEl)
  }

  onBeforeUnmount(() => {
    rafIds.forEach(id => cancelAnimationFrame(id))
    observer?.disconnect()
  })

  return { watch, get reduced() { return prefersReduced } }
}
