/**
 * 粒子网络场（Particle Field）配置
 *
 * 移植自 BioTender scholar-program 的 neural network field，
 * 适配 SciReagent 深色英雄区（teal/cyan 色系，与 hero 渐变文字一致）。
 *
 * 效果：节点缓慢漂浮 + 相近节点动态连线 + 鼠标推开/光晕。
 * 美学：粒子网络（particles.js 流派），均匀铺满，内生于背景。
 */

// ── 节点（Particles）───────────────────────────────────
export const PARTICLES = {
  countDesktop: 45,
  countMobile: 25,
  sizeMin: 0.6,
  sizeMax: 2.1,
  alphaMin: 0.15,
  alphaMax: 0.28,
  velocity: 0.18,           // vx/vy 范围 ±0.18，极慢漂浮
  color: '#5EEAD4',         // 节点光晕色（teal-300）
  coreColor: '#99F6E4',     // 节点核心亮色（teal-200）
}

// ── 连线（Links）───────────────────────────────────────
export const LINKS = {
  maxDistance: 130,         // 节点间距 < 此值时连线
  alphaMax: 0.10,           // 距离 0 时最大 alpha（随距离衰减）
  color: '#5EEAD4',
  width: 0.8,
}

// ── 鼠标交互（桌面）────────────────────────────────────
export const MOUSE = {
  influenceRadius: 200,     // 推开影响半径
  pushForce: 0.04,          // 推开力度
  glowColor: '#38BDF8',     // 鼠标处光晕色（blue）
  glowRadius: 180,
  glowAlpha: 0.07,
}

// ── 背景网格（极淡，结构感）────────────────────────────
export const GRID = {
  size: 80,
  color: 'rgba(94, 234, 212, 0.03)',
}

// ── 性能 ───────────────────────────────────────────────
export const PERF = {
  dprMax: 2,
  dtClamp: 0.05,
}

// ── 响应式 ─────────────────────────────────────────────
export const BREAKPOINT = {
  mobile: 768,
}
