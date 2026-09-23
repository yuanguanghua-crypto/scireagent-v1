/**
 * 同步执行外部命令 —— **必须把子进程 stdin 设为 `'ignore'`**。
 *
 * ★ 2026-09-23 **根因已钉死**：本机（WorkBuddy 会话内）`spawnSync`/`execFileSync` 抛 `EBUSY` 的真因是
 *   **子进程的 stdin 管道**（`stdio[0] === 'pipe'`，也正是这两个 API 的**默认值**）。
 *
 *   判别矩阵（同一条 `cmd.exe /c echo hello`，逐个实测）：
 *   | stdio | 结果 |
 *   |---|---|
 *   | 默认 `['pipe','pipe','pipe']` | **ERR: EBUSY** |
 *   | `['pipe','ignore','ignore']`（**仅 stdin 管道**）| **ERR: EBUSY** |
 *   | `['ignore','pipe','ignore']`（仅 stdout 管道）| **OK** —— 且**能正常读回输出** |
 *   | `['ignore','ignore','pipe']`（仅 stderr 管道）| **OK** |
 *   | `['ignore','pipe','pipe']`（**本助手采用**）| **OK** —— stdout/stderr 均可捕获 |
 *
 *   ⇒ 所以**不是**"同步读输出"的问题（仅 stdout 管道时读回完全正常），而是 **stdin 管道的创建被拦**。
 *   旁证：**异步** `spawn` 用默认管道（含 stdin）**可以**；Python 的 `subprocess` 也正常
 *   ⇒ 只有"**同步 + stdin 管道**"这一组合被拦。
 *
 *   **已排除**（每条都做过实验，非推理）：
 *   · node 注入的 shim（`NODE_OPTIONS` 清空后仍 EBUSY）
 *   · 目标 exe 与路径形态（系统 `ssh`/`cmd.exe`/项目内 venv python；正反斜杠绝对路径都一样）
 *   · 沙箱开关（`dangerouslyDisableSandbox` 放行后仍 EBUSY）
 *   · "进程创建被全面禁止"（Python 与异步 spawn 均正常）
 *
 *   拦截者本体**仍未钉死**（环境线索：`LSBOX_AUDIT_SHMEM=Local\LiteSandbox_Audit_…`），
 *   但**修法已确定、零副作用**：这些调用**从不往子进程 stdin 写数据**，因此把 stdin 关掉即可 ——
 *   既不需要旧版的"临时文件重定向"，也不损失任何能力（stdout/stderr 照常捕获）。
 *
 * ⚠️ 该现象是**动态/间歇**的：2026-09-23 08:1x 那轮 111 条用例还全过，08:45 起 `db-snapshot.cjs`
 *   的 venv python 也开始中招 ⇒ 故**统一收口到本助手**，`prod-db.cjs` / `db-snapshot.cjs` / 各 spec 共用。
 *   细节与影响面见 `e2e/README.md` 坑14。
 */

const { spawnSync } = require('node:child_process')

/**
 * @param {string} cmd 可执行文件（走 PATH 解析）
 * @param {string[]} args
 * @param {{timeout?:number, cwd?:string, env?:NodeJS.ProcessEnv, label?:string}} [opts]
 * @returns {string} stdout 全文（utf8 字符串）
 * @throws 启动失败（`r.error`）或退出码非 0 时抛错，并带上 stderr 片段
 */
function runSync(cmd, args, { timeout = 60000, cwd, env, label = cmd } = {}) {
  const r = spawnSync(cmd, args, {
    // ★ 关键：stdin 必须 `'ignore'` —— 建 stdin 管道是本机 EBUSY 的唯一触发点（见文件头）。
    //   调用方从不往子进程 stdin 写数据，所以这一项**只去掉故障、不损失能力**。
    stdio: ['ignore', 'pipe', 'pipe'],
    encoding: 'utf8',
    maxBuffer: 32 * 1024 * 1024, // 探针输出可能较大（如全表序列普查）
    timeout,
    cwd,
    env,
  })
  if (r.error) {
    const err = r.stderr ? `；stderr: ${String(r.stderr).slice(0, 300)}` : ''
    throw new Error(`${label} 启动失败：${r.error.code || r.error.message}${err}`)
  }
  if (r.status !== 0) {
    const err = r.stderr ? `；stderr: ${String(r.stderr).slice(0, 300)}` : ''
    throw new Error(`${label} 退出码 ${r.status}${err}`)
  }
  return r.stdout || ''
}

module.exports = { runSync }
