/**
 * useParticleField — 粒子网络场（BioTender 移植，零依赖）
 *
 * 节点缓慢漂浮（边界反弹）+ 相近节点动态连线（距离驱动 alpha）+ 鼠标推开/光晕。
 * 命令式 API：build/resize/setMouse/update/draw/drawStatic。
 *
 * O(N²) 连线，N=70 时约 4900 次/帧，60fps 无压力。
 */
import { PARTICLES, LINKS, MOUSE, GRID, BREAKPOINT } from '../config/particleField.config'

const TWO_PI = Math.PI * 2

function rand(a, b) { return a + Math.random() * (b - a) }
function hexA(hex, alpha) {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const bl = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${bl},${Math.max(0, Math.min(1, alpha))})`
}

export function useParticleField() {
  let particles = []
  let width = 0
  let height = 0
  const mouse = { x: 0, y: 0, active: false }

  function isMobile() {
    if (typeof window === 'undefined') return false
    return window.innerWidth < BREAKPOINT.mobile
  }

  function build(w, h) {
    width = w
    height = h
    const count = isMobile() ? PARTICLES.countMobile : PARTICLES.countDesktop
    particles = new Array(count)
    for (let i = 0; i < count; i++) {
      particles[i] = {
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 2 * PARTICLES.velocity,
        vy: (Math.random() - 0.5) * 2 * PARTICLES.velocity,
        r: rand(PARTICLES.sizeMin, PARTICLES.sizeMax),
        a: rand(PARTICLES.alphaMin, PARTICLES.alphaMax),
      }
    }
  }

  function resize(w, h) {
    if (!width || !height || particles.length === 0) { build(w, h); return }
    const sx = w / width, sy = h / height
    width = w
    height = h
    for (const p of particles) { p.x *= sx; p.y *= sy }
  }

  function setMouse(x, y, active) {
    mouse.x = x
    mouse.y = y
    mouse.active = active
  }

  function update() {
    const infR = MOUSE.influenceRadius
    const infR2 = infR * infR
    for (const p of particles) {
      p.x += p.vx
      p.y += p.vy
      if (p.x < 0 || p.x > width) p.vx *= -1
      if (p.y < 0 || p.y > height) p.vy *= -1
      if (mouse.active) {
        const dx = mouse.x - p.x, dy = mouse.y - p.y
        const d2 = dx * dx + dy * dy
        if (d2 < infR2) {
          const f = (1 - Math.sqrt(d2) / infR) * MOUSE.pushForce
          p.x -= dx * f * 0.3
          p.y -= dy * f * 0.3
        }
      }
    }
  }

  function draw(ctx) {
    // 连线（动态距离）
    const maxD = LINKS.maxDistance
    const n = particles.length
    for (let i = 0; i < n; i++) {
      const a = particles[i]
      for (let j = i + 1; j < n; j++) {
        const b = particles[j]
        const dx = a.x - b.x, dy = a.y - b.y
        const d2 = dx * dx + dy * dy
        if (d2 < maxD * maxD) {
          const d = Math.sqrt(d2)
          const alpha = (1 - d / maxD) * LINKS.alphaMax
          ctx.strokeStyle = hexA(LINKS.color, alpha)
          ctx.lineWidth = LINKS.width
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(b.x, b.y)
          ctx.stroke()
        }
      }
    }

    // 节点（光晕 + 核心）
    for (const p of particles) {
      const glowR = Math.max(0.5, p.r * 4)
      const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, glowR)
      grad.addColorStop(0, hexA(PARTICLES.color, p.a * 0.6))
      grad.addColorStop(1, hexA(PARTICLES.color, 0))
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(p.x, p.y, glowR, 0, TWO_PI)
      ctx.fill()

      ctx.fillStyle = hexA(PARTICLES.coreColor, Math.min(1, p.a + 0.1))
      ctx.beginPath()
      ctx.arc(p.x, p.y, Math.max(0.3, p.r), 0, TWO_PI)
      ctx.fill()
    }

    // 鼠标光晕
    if (mouse.active) {
      const grad = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, MOUSE.glowRadius)
      grad.addColorStop(0, hexA(MOUSE.glowColor, MOUSE.glowAlpha))
      grad.addColorStop(1, hexA(MOUSE.glowColor, 0))
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, width, height)
    }
  }

  /** reduced-motion：静态绘制一帧（节点不动、不响应鼠标） */
  function drawStatic(ctx) {
    mouse.active = false
    draw(ctx)
  }

  return { build, resize, setMouse, update, draw, drawStatic }
}
