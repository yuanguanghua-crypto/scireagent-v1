/**
 * PO E2E 夹具加载器 —— 惰性读取 + 缺失时给出可执行提示（而非收集期ENOENT 崩掉整个 e2e）。
 *
 * ## 为什么需要它
 * `e2e_po_fixture.json` 由 `backend/seed_e2e_po_fixture.py` 生成，**刻意不入库**
 * （见根 `.gitignore`：含 dev 专属的 product_id/sku_id/inventory_id，入库会在
 * 新 clone / 生产机上指向**不存在的行** ⇒ 比缺文件更危险）。
 *
 * 历史缺陷：三个 spec（po-lifecycle.api / po-lifecycle.ui / ops-inventory）在**模块顶层**
 * `JSON.parse(fs.readFileSync(...))`。Playwright 先**收集全部 spec** 再按 `--grep` 筛选，
 * 于是即使只跑 `-g "@prod-ok"`（一个 fixture 都不需要），也会在**收集阶段**抛
 *   `Error: ENOENT: no such file or directory, open '.../e2e_po_fixture.json'`
 * ⇒ 整个 e2e 目录跑不起来（实测于生产机47.82.156.48）。
 *
 * 本模块把读取推迟到真正需要时，并在缺失时给出**怎么生成**的提示。
 */
const fs = require('fs');
const path = require('path');

const FIXTURE_PATH = path.join(__dirname, '..', '..', 'e2e_po_fixture.json');

const GENERATE_HINT =
  `缺少 PO E2E 夹具 ${FIXTURE_PATH}。\n` +
  '  该文件**刻意不入库**（含 dev 专属 id，入库会指向不存在的行）。本地生成：\n' +
  '    cd src_claude/backend\n' +
  "    DB_ENGINE=sqlite venv/Scripts/python.exe manage.py shell -c \"exec(open('seed_e2e_po_fixture.py').read())\"\n" +
  '  ⚠️ 该夹具供`@local-only` 的 PO 用例使用；跑生产回归（`-g "@prod-ok"`）不需要它。';

/** 惰性读取；不存在返回 null（**不抛**），由调用方 test.skip 给出提示。 */
function loadFixture() {
  try {
    return JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));
  } catch {
    return null;
  }
}

module.exports = { FIXTURE_PATH, GENERATE_HINT, loadFixture };