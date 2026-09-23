/**
 * 同步执行外部命令，**但不给子进程建 stdio 管道**。
 *
 * ★ 2026-09-23 修「`spawnSync … EBUSY`」：本机（WorkBuddy 会话内）实测 ——
 *   `execFileSync`/`spawnSync` 在**默认 `stdio:'pipe'`** 下会稳定抛 `EBUSY`；
 *   把输出**重定向到临时文件**（`stdio:['ignore', fd, fd2]`，即不建管道）就恢复正常。
 *
 * 实测矩阵（同一条 `ssh -V`）：
 *   | 变体 | 结果 |
 *   | `spawnSync('ssh', …, 默认 pipe)` | **ERR: EBUSY** |
 *   | `spawnSync('ssh', …, stdio:'ignore')` | OK status=0 |
 *   | `spawnSync('cmd.exe', …, stdio:'ignore')` | OK status=1 |
 *   | `spawnSync('ssh', …, stdio:'inherit')` | OK status=0 |
 *   | `spawnSync(venv python, …, 文件 fd)` | OK（本助手用的就是这条） |
 *
 * **已排除**（每条都做过实验，非推理）：node 注入的 shim（清空 `NODE_OPTIONS` 仍挂）、
 * 目标 exe 与路径形态（系统 ssh / 项目内 venv python / 正反斜杠都一样）、
 * 沙箱开关（`dangerouslyDisableSandbox` 放行后仍挂）、
 * "进程创建被全面禁止"（Python 的 `subprocess` 与 node 的**异步** `spawn` 都正常）。
 * ⇒ 只有"**同步 + 管道**"这个组合被拦。
 *
 * ⚠️ 该现象是**动态/间歇**的：2026-09-23 08:1x 那轮 111 用例还全过，08:45 起
 *    `db-snapshot.cjs` 的 venv python 也开始报 EBUSY ⇒ 故本助手被 `prod-db.cjs`
 *    与 `db-snapshot.cjs` 共用。详见 `e2e/README.md` 坑14。
 */

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

/**
 * @param {string} cmd 可执行文件（走 PATH 解析）
 * @param {string[]} args
 * @param {{timeout?:number, cwd?:string, env?:NodeJS.ProcessEnv, label?:string}} [opts]
 * @returns {string} stdout 全文
 * @throws 启动失败（`r.error`）或退出码非 0 时抛错，并带上 stderr 片段
 */
function runSync(cmd, args, { timeout = 60000, cwd, env, label = cmd } = {}) {
  const base = path.join(
    os.tmpdir(),
    `e2e_sync_${process.pid}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  )
  const outFile = `${base}.out`
  const errFile = `${base}.err`
  const outFd = fs.openSync(outFile, 'w')
  const errFd = fs.openSync(errFile, 'w')
  try {
    const r = spawnSync(cmd, args, { stdio: ['ignore', outFd, errFd], timeout, cwd, env })
    const out = fs.readFileSync(outFile, 'utf8')
    const err = fs.readFileSync(errFile, 'utf8')
    if (r.error) {
      throw new Error(
        `${label} 启动失败：${r.error.code || r.error.message}${err ? `；stderr: ${err.slice(0, 300)}` : ''}`
      )
    }
    if (r.status !== 0) {
      throw new Error(
        `${label} 退出码 ${r.status}${err ? `；stderr: ${err.slice(0, 300)}` : ''}`
      )
    }
    return out
  } finally {
    // ⚠️ 顺序：**先 close 再 unlink**（Windows 上文件仍被占用时 unlink 会失败）
    try { fs.closeSync(outFd) } catch { /* ignore */ }
    try { fs.closeSync(errFd) } catch { /* ignore */ }
    try { fs.unlinkSync(outFile) } catch { /* ignore */ }
    try { fs.unlinkSync(errFile) } catch { /* ignore */ }
  }
}

module.exports = { runSync }
