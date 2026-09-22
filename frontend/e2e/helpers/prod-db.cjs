/**
 * P1 基建 · **生产只读计数探针**（R2 生产环境上实现 D-DB / N-负向 断言）
 *
 * 为什么另开一个 helper（不直接用 db-snapshot.cjs）：
 *   `db-snapshot.cjs` 有**护栏**——目标非 localhost 时主动抛错，防止把本地 sqlite 计数
 *   当成生产判据（假阳）。生产要断言「只读 Δ0」必须走**容器内只读 SELECT**：
 *     ssh <生产> 'docker exec scireagent-db-1 psql -U scireagent -d scireagent -tAc "..."'
 *
 * 铁律：**只读**。本 helper 只发 `SELECT count(*)`，绝不含任何写语句。
 * 表名**无 app 前缀**（与生产 PG 实况一致；见 _probe_dgroup/counts.sql 实测）。
 *
 * 性能：ssh 每次约 2–4s ⇒ **只在代表性用例（D16）上跑前后各一次**，勿逐例调用。
 *
 * 环境变量（均有生产默认值，可覆盖）：
 *   E2E_SSH_KEY / E2E_SSH_HOST / E2E_DB_CONTAINER / E2E_DB_USER / E2E_DB_NAME / E2E_DB_TABLES
 *
 * 借用方式（D16 用例内）：
 *   const { prodCounts, TABLES } = require('./helpers/prod-db.cjs')
 *   const before = prodCounts(); await enrich(); const after = prodCounts()
 *   expectDelta(before, after, zeroSpec(before), 'D16 enrich 只读')
 */
const { execFileSync } = require('node:child_process')

const SSH_KEY = process.env.E2E_SSH_KEY || 'C:/Users/yuankaifeng/.ssh/scireagent_deploy_ed25519'
const SSH_HOST = process.env.E2E_SSH_HOST || 'admin@47.82.156.48'
const DB_CONTAINER = process.env.E2E_DB_CONTAINER || 'scireagent-db-1'
const PG_USER = process.env.E2E_DB_USER || 'scireagent'
const PG_DB = process.env.E2E_DB_NAME || 'scireagent'

/** 默认关注表：与 P0 剧本组 J1/D16 一致（product 血缘 + 知识权威表 + 审计） */
const TABLES = (
  process.env.E2E_DB_TABLES ||
  'product,product_protocol,product_method,product_method_relation,audit_log,protocol,method'
).split(',')

/** 目标必须是**生产**（非 localhost），否则拒绝——避免误用（判错方向：宁可拒绝）。 */
function assertProdTarget() {
  const base = process.env.E2E_API_BASE || ''
  let host = ''
  try {
    host = new URL(base).hostname
  } catch {
    host = String(base)
  }
  if (!host || ['localhost', '127.0.0.1', '::1', '0.0.0.0'].includes(host)) {
    throw new Error(
      `prodCounts 只用于【生产】；当前 E2E_API_BASE=${base || '(空)'}（host=${host || '空'}）是本地目标——\n` +
        '本地请改用 db-snapshot.cjs 的 dbSnapshot()。'
    )
  }
}

/**
 * 取生产库只读计数快照。
 * @param {string[]} [tables] 关注表；默认 TABLES
 * @returns {Record<string, number>}  如 { product: 125, audit_log: 102, ... }
 */
function prodCounts(tables = TABLES) {
  assertProdTarget()
  // 只读：单条 UNION ALL 的 SELECT count(*)
  const sql = tables.map((t) => `SELECT '${t}' AS t, count(*) FROM ${t}`).join(' UNION ALL ')
  const remote = `docker exec ${DB_CONTAINER} psql -U ${PG_USER} -d ${PG_DB} -tAc "${sql}"`
  // argv 数组直传 ssh（不经本地 shell）⇒ 无引号地狱；远端命令在单引号内由远端 sh 解析
  const args = [
    '-i', SSH_KEY,
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'BatchMode=yes',
    '-o', 'ConnectTimeout=10',
    SSH_HOST,
    remote,
  ]
  const out = execFileSync('ssh', args, { encoding: 'utf8', timeout: 60000 })
  const res = {}
  for (const line of String(out).split(/\r?\n/)) {
    const [t, v] = line.split('|')
    if (t && t.trim()) res[t.trim()] = parseInt(v, 10)
  }
  const missing = tables.filter((t) => !(t in res))
  if (missing.length) {
    throw new Error(`prodCounts 未取到表：${missing.join(',')}；原始输出：${String(out).slice(0, 200)}`)
  }
  return res
}

module.exports = { prodCounts, TABLES, assertProdTarget, SSH_KEY, SSH_HOST, DB_CONTAINER }
