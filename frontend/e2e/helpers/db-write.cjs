/**
 * ★ 夹具**播种**（写库）—— 与 `db-snapshot.cjs` 的「只读契约」**严格分开**，勿混用。
 *
 * 为什么需要它（2026-09-24 实测）：
 *   `helpers/db-snapshot.cjs` 的 `dbQuery` 有明文纪律：「只允许 SELECT / ORM 读，
 *   禁止 save/create/update/delete」（靠调用方自律）。但有些 P0 用例的**夹具前提**必须
 *   真的在库里造出数据行（如"产品已有 INHERITED 知识链接，保存时不得丢"），
 *   而 API 层已没有可用的构造手段 —— 见下。
 *
 * 背景事实（本次踩到的行为变更，**不是** spec 写错）：
 *   `product-save-keeps-links.spec.cjs` 的头部原记录「`POST /products/ {method_ids:[54]}`
 *   建夹具后 ProductProtocol=753」是 2026-09-24 10:03 的**真实实测**。
 *   但 `367e5f4`（"低分不落库：零证据的协议不再写入 ProductProtocol"）落地后：
 *     `relevance.py:523` `if is_evidence_free(fused): continue`，而 `is_evidence_free` 等价于
 *     `tier == 'weak'`；新建产品在 `compute_axis_a=None / b=0.0 / c=0.5` 下算出的
 *     `score=0.1`、`tier='weak'` ⇒ **全部被跳过** ⇒ `recompute_product` 返回 0。
 *   即：**新产品经 API 建好后，其 INHERITED 行数 = 0**（要等离线 emb3 补算才会有）。
 *   ⇒ "保存不得丢链"这一 P0 不变量不能再靠"派生"来铺夹具，必须**直接播种**。
 *
 * 纪律：
 *   · 只用于**本地 dev**（沿用 `assertLocalTarget()` 同一护栏，目标非 localhost 直接拒绝）。
 *   · 只允许写 `E2E-` 前缀夹具产品；调用方负责清理（按 id 硬删，产品级 CASCADE）。
 *   · 播种内容一律 `link_source='inherited'`（本模块只做这件事），不碰非夹具行。
 */
const { runSync } = require('./sync-spawn.cjs')
const path = require('node:path')
const { BACKEND, assertLocalTarget } = require('./db-snapshot.cjs')

const PY = path.join(BACKEND, 'venv', 'Scripts', 'python.exe')

/** 执行一段**会写库**的 Python（必须 print `__SNAP__` + JSON）。 */
function dbExec(pyCode, label = 'dbExec') {
  assertLocalTarget()
  const out = runSync(PY, ['-B', 'manage.py', 'shell', '-c', pyCode], {
    cwd: BACKEND,
    env: { ...process.env, DB_ENGINE: 'sqlite', PYTHONDONTWRITEBYTECODE: '1' },
    timeout: 60000,
    label: `dbExec(${label}) python`,
  })
  const line = String(out).split(/\r?\n/).find((l) => l.startsWith('__SNAP__'))
  if (!line) {
    throw new Error(`dbExec(${label}) 未取到标记行；原始输出前 300 字：` + String(out).slice(0, 300))
  }
  return JSON.parse(line.slice('__SNAP__'.length))
}

/**
 * 给夹具产品播种 N 条 INHERITED `ProductProtocol` 行。
 *
 * 取哪些协议？**取该产品方法链在 `MethodProtocol` 上的真实派生集**（而不是随便挑协议）——
 * 这样播种出来的行正好落在 `_refresh_inherited_bridges` 的 `derived_ids` 内，
 * 与"按当前链收敛"的既有语义一致：**链没变 ⇒ 不该被删**；链被清空 ⇒ 应被删。
 *
 * @param {number} productId 夹具产品 id（`E2E-` 前缀）
 * @param {number} count 播种条数
 * @returns {{seeded:number, pp:number, ppI:number, pool:number}}
 */
function seedInheritedProtocols(productId, count) {
  const code = [
    'import json',
    'from apps.bridges.models import ProductMethod, MethodProtocol, ProductProtocol',
    `pid = ${Number(productId)}`,
    'mids = list(ProductMethod.objects.filter(product_id=pid).values_list("method_id", flat=True))',
    'pool = list(MethodProtocol.objects.filter(method_id__in=mids)'
      + '.values_list("protocol_id", flat=True).distinct())',
    `pids = pool[:${Number(count)}]`,
    'seeded = 0',
    'for pr in pids:',
    '    ProductProtocol.objects.update_or_create(',
    '        product_id=pid, protocol_id=pr,',
    '        defaults=dict(link_source="inherited", tier="document", relevance_score=0.9,',
    '                      score_a=0.9, score_b=0.0, score_c=None, literature_count=0,',
    '                      relevance_basis="e2e_seed"))',
    '    seeded += 1',
    'print("__SNAP__" + json.dumps({',
    '    "seeded": seeded, "pool": len(pool),',
    '    "pp": ProductProtocol.objects.filter(product_id=pid).count(),',
    '    "ppI": ProductProtocol.objects.filter(product_id=pid, link_source="inherited").count(),',
    '}))',
  ].join('\n')
  return dbExec(code, `seedInheritedProtocols(${productId},${count})`)
}

module.exports = { dbExec, seedInheritedProtocols, PY }
