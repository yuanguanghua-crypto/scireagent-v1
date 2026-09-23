#!/usr/bin/env node
/**
 * 闸门审计（gate-audit）
 * ---------------------------------------------------------------------------
 * 目的：让「漏跑」不可能静默发生。
 *
 * 背景：跑批脚本用 `-g "@readonly"` / `-g "@write"` / `-g "@local-only"` 过滤，
 *       任何**没有 tier 标签**（@readonly / @write / @obsolete）的用例都不会被
 *       选中，也不会报错 —— 即「静默漏跑」。
 *
 * 做法：用 Playwright 的 JSON reporter 列出全部用例（--list，不执行浏览器），
 *       逐条检查其 tags 是否至少含 readonly / write / obsolete 之一。
 *       缺失即打印明细并以退出码 1 失败 ⇒ `test:e2e:local` 会在此处直接中断，
 *       而不是带着缺口继续跑。
 *
 * 说明：JSON reporter 会把 **describe 级** 与 **test 标题级** 标签一并归到
 *       spec.tags（已实测：`test(title, { tag })` 与标题内嵌 `@tag` 都会被 `-g`
 *       选中、且都进 spec.tags），因此本审计对两种标注写法均有效。
 *
 * 范围：testMatch = e2e/**\/*.spec.cjs（**含子目录**）。`inventory-driven/` 的
 *       历史遗留套件已逐条补 `@obsolete`（理由见 GATE.md），因此**不再特殊排除** ——
 *       它和其他 spec 一视同仁：有 tier 标签则通过，缺则审计失败。
 *       ⇒ 任何新加的、忘记打标签的用例（无论在哪个子目录）都会被这里挡下。
 */
const { execFileSync } = require('node:child_process');
const path = require('node:path');

const FRONTEND_DIR = path.join(__dirname, '..');
const CLI = path.join(FRONTEND_DIR, 'node_modules', '@playwright', 'test', 'cli.js');

// tier = 决定「是否被闸门选中 / 是否被显式排除」的标签，三者必居其一。
const TIER = new Set(['readonly', 'write', 'obsolete']);

function runList() {
  const args = [CLI, 'test', '--list', '--project=chromium', '--reporter=json'];
  try {
    return execFileSync(process.execPath, args, {
      cwd: FRONTEND_DIR,
      encoding: 'utf8',
      maxBuffer: 128 * 1024 * 1024,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (err) {
    // --list 正常应 exit 0；异常时尽量取回 stdout 以给出可读错误。
    const out = (err.stdout || '').toString();
    if (out.trim().startsWith('{')) return out;
    console.error('gate-audit: 无法获取用例清单（playwright --list 失败）：');
    console.error((err.stderr || err.message || '').toString());
    process.exit(2);
  }
}

function walk(suite, inheritedFile, visit) {
  const file = suite.file || inheritedFile || '';
  for (const spec of suite.specs || []) visit(file, spec);
  for (const sub of suite.suites || []) walk(sub, file, visit);
}

function rel(p) {
  return p ? path.relative(path.join(__dirname), p).replace(/\\/g, '/') : '';
}

const raw = runList();
let json;
try {
  json = JSON.parse(raw);
} catch (e) {
  console.error('gate-audit: JSON 解析失败：', e.message);
  process.exit(2);
}

// ★ 收集阶段一旦报错（某 spec 语法/require 失败），Playwright 的 JSON 里
//   suites 会为 0、errors 非空 —— 若只看 offenders 就会「0 例全过」而静默放行。
//   这里显式拦下：清单不完整 = 审计不可信 = 失败。
if (Array.isArray(json.errors) && json.errors.length) {
  console.error('');
  console.error(`gate-audit: ✘ Playwright 收集阶段报错 ${json.errors.length} 条，用例清单不完整，审计不可信：`);
  for (const e of json.errors) console.error('  - ' + String(e.message || e).split('\n')[0]);
  console.error('⇒ 请先修复这些 spec 的加载错误，再重跑本审计。');
  process.exit(3);
}

const offenders = [];
let total = 0;

for (const suite of json.suites || []) {
  walk(suite, suite.file, (file, spec) => {
    total += 1;
    const relFile = rel(file) || file;
    const tags = spec.tags || [];
    const hasTier = tags.some((t) => TIER.has(t));
    if (!hasTier) {
      offenders.push(`${relFile} :: ${spec.title} :: tags=[${tags.join(',')}]`);
    }
  });
}

if (total === 0) {
  console.error('gate-audit: ✘ 清单为 0 个用例 —— 配置/收集异常，无法证明「无漏跑」，判为失败。');
  process.exit(3);
}

if (offenders.length) {
  console.error('');
  console.error(`gate-audit: ✘ 发现 ${offenders.length}/${total} 个**未标注 tier 的用例**（@readonly/@write/@obsolete 皆无）：`);
  for (const o of offenders) console.error('  - ' + o);
  console.error('⇒ 这些用例既不会被 -g "@local-only" 跑到，也不会被 @obsolete 排除 = 静默漏跑。');
  console.error('   请为所在文件/用例补上 tier 标签，或在 GATE.md 登记为闸门外并标注 @obsolete。');
  process.exit(1);
}

console.log('');
console.log(`gate-audit: ✔ OK — 范围内 ${total} 个用例全部带 tier 标签（@readonly/@write/@obsolete）。`);
