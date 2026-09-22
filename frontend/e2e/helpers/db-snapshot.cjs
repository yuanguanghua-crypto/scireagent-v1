/**
 * P1 基建 · DB 快照（只读取数，**不新增后端端点、不改 app 代码**）
 *
 * 为什么不用 API 取计数：后端 `meta.pagination.count` 只覆盖有列表端点的表
 * （product 可以），但 `audit_log` / bridges 三表**没有公开端点** ⇒ 通用计数只能走 ORM。
 *
 * 实现：以子进程调用本地 Django shell（`manage.py shell -c`），用 argv 数组传代码
 * ⇒ **不经过 shell，无引号地狱**；只 SELECT，不写库。
 *
 * 适用范围：**本地 dev（R1 / R3）** —— 生产（R2）的 D-断言由「跑前跑后容器内只读探针」
 * 覆盖，并在报告里注明来源（判据来源需可追溯，见 P0 §0）。
 */
const { execFileSync } = require('node:child_process')
const path = require('node:path')

const BACKEND = path.resolve(__dirname, '../../../backend')
const PY = path.join(BACKEND, 'venv', 'Scripts', 'python.exe')

/** 默认快照的表 → ORM 计数表达式 */
const DEFAULT_PY = [
  "import json",
  "from apps.commerce.models import Product, AuditLog",
  "from apps.bridges.models import ProductProtocol, ProductMethod, ProductMethodRelation",
  "print('__SNAP__' + json.dumps({",
  "  'product': Product.objects.count(),",
  "  'product_archived': Product.objects.filter(archived=True).count(),",
  "  'product_active': Product.objects.filter(archived=False).count(),",
  "  'audit_log': AuditLog.objects.count(),",
  "  'product_protocol': ProductProtocol.objects.count(),",
  "  'product_method': ProductMethod.objects.count(),",
  "  'product_method_relation': ProductMethodRelation.objects.count(),",
  "}))",
].join('\n')

/**
 * 目标是否为本机 dev。判定依据：E2E_API_BASE 的 host ∈ {localhost,127.0.0.1,::1}。
 * 判错方向要「宁可拒绝」——拒绝最多是漏跑，错认则是假阳。
 */
function assertLocalTarget() {
  const base = process.env.E2E_API_BASE || 'http://localhost:8000'
  let host = ''
  try {
    host = new URL(base).hostname
  } catch {
    host = String(base)
  }
  const isLocal = ['localhost', '127.0.0.1', '::1', '0.0.0.0'].includes(host)
  if (!isLocal) {
    throw new Error(
      `dbSnapshot 只读【本地 dev sqlite】，当前目标却是 ${base}（host=${host}）——\n` +
        '若要对生产做 D-DB/N-负向 断言，必须改用「容器内只读探针」（跑前跑后各取一次计数），\n' +
        '绝不能把本地库计数当作生产判据（那是假阳）。详见 e2e/README.md §3。'
    )
  }
}

/**
 * 取本地 dev 库的只读快照。
 * @param {string[]} [tables] 预留：仅供调用方声明关注表（当前统一返回全量 7 项）
 * @returns {Record<string, number>}
 */
function dbSnapshot(tables) {
  // ★防误用护栏（P1）：本函数只读【本地 dev sqlite】。
  //   若本次运行目标是生产（E2E_API_BASE 非 localhost），拿本地库当生产判据会
  //   产出**假阳**（最危险的一类错）⇒ 直接拒绝，要求改用容器内只读探针。
  assertLocalTarget()
  const out = execFileSync(PY, ['-B', 'manage.py', 'shell', '-c', DEFAULT_PY], {
    cwd: BACKEND,
    env: { ...process.env, DB_ENGINE: 'sqlite', PYTHONDONTWRITEBYTECODE: '1' },
    encoding: 'utf8',
    timeout: 60000,
  })
  const line = String(out).split(/\r?\n/).find((l) => l.startsWith('__SNAP__'))
  if (!line) {
    throw new Error('dbSnapshot 未取到标记行；原始输出前 200 字：' + String(out).slice(0, 200))
  }
  const snap = JSON.parse(line.slice('__SNAP__'.length))
  if (tables && tables.length) {
    return Object.fromEntries(Object.entries(snap).filter(([k]) => tables.includes(k)))
  }
  return snap
}

module.exports = { dbSnapshot, assertLocalTarget, BACKEND }
