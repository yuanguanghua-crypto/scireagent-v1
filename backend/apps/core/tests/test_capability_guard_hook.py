r"""
capability-guard pre-commit hook + 安装脚本的回归测试。

这个 hook 固化的是一次真实事故的**机制性教训**：
  `scripts/capability_guard.py` 已落地 1398 行 + 15 个自测，
  但 `.git/hooks/` 0 个自定义 hook、`.github/workflows/` 0 个 workflow
  ⇒ **零自动化接入**，只能靠人记得手动跑。
  而「零引用 ≠ 无能力」当天已经付出两项能力丢失的代价
  （批量 AI + goals/apps UI）。
  ⇒ 一个「人记得才会用」的闸门，等于没有闸门。

⚠️ 这个 hook 的测试不能只测"文本里有某句话"，必须测**可执行行为**：
   在临时 git 仓库里真的暂存一个删除、真的调 hook、真的看退出码。
   静态检查测不出 `ValueError: path is on mount 'E:'` 这类
   **只在 Windows + bash + 真仓库**下才暴露的问题 —— 而那正是今天实际踩到的。

测试策略：在 tmp 目录建一个**独立 git 仓库**，把模板 hook 复制进去当
`.git/hooks/pre-commit`，用它自带的假闸门脚本控制返回码。
这样测试**不依赖真实仓库状态**，也不会在真仓库里制造删除。
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase

REPO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
)
TEMPLATE = os.path.join(REPO, "scripts", "hooks", "pre-commit-capability-guard")
INSTALLER = os.path.join(REPO, "scripts", "install_git_hooks.py")
GITATTRS = os.path.join(REPO, ".gitattributes")

def _find_bash():
    """找一个**真 POSIX shell**，跳过 Windows 上会误导的 bash 启动器。

    ⚠️ 实测踩到的坑：`shutil.which("bash")` 在 Windows 上会返回
       `C:\\Windows\\System32\\bash.exe` —— 那是 **WSL 启动器**，
       它不是 POSIX shell，用它跑 git hook 会得到一堆莫名其妙的错误。
       ⇒ 必须显式找 Git Bash。
    """
    exe = shutil.which("bash")
    if exe:
        base = os.path.basename(exe).lower()
        parent = os.path.basename(os.path.dirname(exe)).lower()
        if base == "bash.exe" and ("system32" in parent or "windowsapps" in parent):
            exe = None                     # WSL 启动器，不可用
    if exe:
        return exe
    # 常见 Git 安装位置兜底
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files\Git\usr\bin\bash.exe"):
        if os.path.isfile(cand):
            return cand
    # 从 PATH 里逐个目录找，避开 system32 / WindowsApps
    for d in (os.environ.get("PATH") or "").split(os.pathsep):
        p = os.path.join(d.strip('"'), "bash.exe")
        if os.path.isfile(p):
            low = d.lower()
            if "system32" in low or "windowsapps" in low:
                continue
            return p
    return None


BASH = _find_bash()
HAS_BASH = BASH is not None


def _run(cmd, cwd, env=None, check=False):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=e)
    if check and p.returncode != 0:
        raise AssertionError(f"{cmd}\nstdout={p.stdout}\nstderr={p.stderr}")
    return p


class TemplateFileTests(SimpleTestCase):
    """模板本身必须入库（`.git/hooks/` 不入库，所以模板是关键）。"""

    def test_template_exists_in_repo(self):
        self.assertTrue(os.path.isfile(TEMPLATE),
                        "hook 模板必须入库，否则别人 clone 后无从安装")

    def test_template_is_tracked_by_git(self):
        p = _run(["git", "ls-files", "--error-unmatch",
                  "scripts/hooks/pre-commit-capability-guard"],
                 cwd=REPO)
        # 未提交时这个测试会红 —— 那正是提醒"别忘了提交模板"的信号
        self.assertEqual(p.returncode, 0,
                         "hook 模板没有被 git 跟踪 ⇒ 它不会随仓库分发")

    def test_template_has_lf_only(self):
        with open(TEMPLATE, "rb") as f:
            raw = f.read()
        self.assertNotIn(b"\r\n", raw,
                         "模板含 CRLF。core.autocrlf=true 下检出后 hook 会在 "
                         "Git Bash 里报 $'\\r': command not found")

    def test_template_starts_with_shebang(self):
        with open(TEMPLATE, "r", encoding="utf-8") as f:
            first = f.readline()
        self.assertTrue(first.startswith("#!"), "hook 必须有 shebang")
        self.assertIn("bash", first)

    def test_gitattributes_forces_lf_on_hooks(self):
        """★ 这是 Windows 上 hook 能否执行的关键约束。

        本仓库 core.autocrlf=true（实测），不声明 eol=lf 的话，
        模板检出后就是 CRLF 的，hook 直接失效。
        """
        self.assertTrue(os.path.isfile(GITATTRS),
                        "缺少 .gitattributes ⇒ CRLF 会搞坏 hook")
        with open(GITATTRS, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("scripts/hooks/", content)
        self.assertIn("eol=lf", content)

    def test_template_documents_all_escape_hatches(self):
        with open(TEMPLATE, "r", encoding="utf-8") as f:
            c = f.read()
        self.assertIn("SKIP_CAPABILITY_GUARD", c, "必须有环境变量逃生口")
        self.assertIn("CAPABILITY_GUARD_FORCE", c)
        self.assertIn("--no-verify", c)

    def test_failure_message_explains_orphan_module_rule(self):
        """★ 必须在提示里讲清「孤儿模块不算入口」，否则有人会用它骗过闸门。"""
        with open(TEMPLATE, "r", encoding="utf-8") as f:
            c = f.read()
        self.assertIn("孤儿", c,
                      "失败提示必须说明孤儿模块不算入口")


class HookBehaviourTests(SimpleTestCase):
    """★ 在真实 git 仓库里跑 hook，验证退出码与触发条件。"""

    def setUp(self):
        if not HAS_BASH:
            self.skipTest("本机没有 bash，无法执行 hook")
        self.tmp = tempfile.mkdtemp(prefix="hook_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "scripts"), exist_ok=True)
        _run(["git", "init", "-q"], cwd=self.repo, check=True)
        _run(["git", "config", "user.email", "t@t"], cwd=self.repo)
        _run(["git", "config", "user.name", "t"], cwd=self.repo)

        # 复制模板当 hook
        hooks = os.path.join(self.repo, ".git", "hooks")
        os.makedirs(hooks, exist_ok=True)
        self.hook = os.path.join(hooks, "pre-commit")
        shutil.copy(TEMPLATE, self.hook)
        st = os.stat(self.hook)
        os.chmod(self.hook, st.st_mode | stat.S_IXUSR | stat.S_IXGRP)

        # 装一个**假闸门**：用 FAKE_RC 控制返回码，并留下调用痕迹
        guard = os.path.join(self.repo, "scripts", "capability_guard.py")
        with open(guard, "w", encoding="utf-8") as f:
            f.write(
                "import os, sys\n"
                "open(os.path.join(os.path.dirname(__file__), '_guard_called'),"
                " 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                "rc = int(os.environ.get('FAKE_RC', '0'))\n"
                "if rc == 2:\n"
                "    # 模拟真实的未捕获异常：Python 退出码也是 1\n"
                "    raise ValueError(\"path is on mount 'E:', start on mount 'C:'\")\n"
                "print('FAKE GUARD OUTPUT rc=%d' % rc)\n"
                "sys.exit(rc)\n"
            )
        self.called = os.path.join(self.repo, "scripts", "_guard_called")

    def _run_hook(self, env=None):
        return _run([BASH, self.hook], cwd=self.repo, env=env)

    def test_no_deletion_means_guard_never_runs(self):
        """★ 核心性能约束：不删文件时绝不能跑闸门（它要 2~4 秒）。"""
        open(os.path.join(self.repo, "a.txt"), "w").close()
        _run(["git", "add", "a.txt"], cwd=self.repo)
        p = self._run_hook()
        self.assertEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(self.called),
                         "没有删除却跑了闸门 ⇒ 每次提交都会慢 2~4 秒")
        self.assertNotIn("capability-guard", p.stderr)

    def test_deletion_triggers_guard_with_audit_and_paths(self):
        """★ 触发时必须用 --audit（文件已从工作区消失，只能从 git 取回）。"""
        victim = os.path.join(self.repo, "doomed.js")
        with open(victim, "w") as f:
            f.write("console.log(1)\n")
        _run(["git", "add", "doomed.js"], cwd=self.repo)
        _run(["git", "commit", "-qm", "add", "--no-verify"], cwd=self.repo)
        os.remove(victim)
        _run(["git", "add", "-A"], cwd=self.repo)

        p = self._run_hook()
        self.assertTrue(os.path.exists(self.called), "有删除却没触发闸门")
        with open(self.called, "r", encoding="utf-8") as f:
            argv = f.read()
        self.assertIn("--audit", argv, "必须用 --audit 模式")
        self.assertIn("--paths", argv)
        self.assertIn("doomed.js", argv)
        self.assertIn("--git-rev", argv)

    def test_skip_env_var_bypasses_guard_entirely(self):
        victim = os.path.join(self.repo, "doomed.js")
        with open(victim, "w") as f:
            f.write("x\n")
        _run(["git", "add", "doomed.js"], cwd=self.repo)
        _run(["git", "commit", "-qm", "add", "--no-verify"], cwd=self.repo)
        os.remove(victim)
        _run(["git", "add", "-A"], cwd=self.repo)

        p = self._run_hook(env={"SKIP_CAPABILITY_GUARD": "1"})
        self.assertEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(self.called),
                         "逃生口必须真的跳过闸门")
        self.assertIn("未经闸门检查", p.stderr,
                      "跳过时必须留下痕迹，不能静默")

    def test_force_env_var_lets_block_through_but_keeps_warning(self):
        victim = os.path.join(self.repo, "doomed.js")
        with open(victim, "w") as f:
            f.write("x\n")
        _run(["git", "add", "doomed.js"], cwd=self.repo)
        _run(["git", "commit", "-qm", "add", "--no-verify"], cwd=self.repo)
        os.remove(victim)
        _run(["git", "add", "-A"], cwd=self.repo)

        p = self._run_hook(env={"FAKE_RC": "1", "CAPABILITY_GUARD_FORCE": "1"})
        self.assertEqual(p.returncode, 0)
        self.assertIn("强制放行", p.stderr, "强制放行必须仍有告警")

    def test_block_exits_nonzero_with_guidance(self):
        victim = os.path.join(self.repo, "doomed.js")
        with open(victim, "w") as f:
            f.write("x\n")
        _run(["git", "add", "doomed.js"], cwd=self.repo)
        _run(["git", "commit", "-qm", "add", "--no-verify"], cwd=self.repo)
        os.remove(victim)
        _run(["git", "add", "-A"], cwd=self.repo)

        p = self._run_hook(env={"FAKE_RC": "1"})
        self.assertEqual(p.returncode, 1, "BLOCK 必须阻止提交")
        err = p.stderr
        self.assertIn("孤儿", err)
        self.assertIn("SKIP_CAPABILITY_GUARD", err)

    def test_guard_crash_is_not_reported_as_block(self):
        """★ 实测踩到的坑：Python 未捕获异常退出码**也是 1**。

        若把 crash 说成「失去了能力入口」，人会以为「那就是要删的」而绕过
        ⇒ crash 反而成了放行通道。必须靠 Traceback 归因。
        """
        victim = os.path.join(self.repo, "doomed.js")
        with open(victim, "w") as f:
            f.write("x\n")
        _run(["git", "add", "doomed.js"], cwd=self.repo)
        _run(["git", "commit", "-qm", "add", "--no-verify"], cwd=self.repo)
        os.remove(victim)
        _run(["git", "add", "-A"], cwd=self.repo)

        p = self._run_hook(env={"FAKE_RC": "2"})
        self.assertEqual(p.returncode, 1)
        # 闸门原始输出（含 traceback）走 stdout；归因提示走 stderr
        self.assertIn("Traceback", p.stdout)
        self.assertIn("崩溃", p.stderr, "必须把 crash 与 BLOCK 区分开")
        self.assertIn("不是 BLOCK", p.stderr)
        self.assertNotIn("失去唯一前端入口", p.stderr,
                         "crash 时不该说成 BLOCK，否则人会以为可以放心绕过")

    def test_missing_guard_is_fail_closed(self):
        """闸门不存在时必须拦（fail-closed），不能默默放行。"""
        os.remove(os.path.join(self.repo, "scripts", "capability_guard.py"))
        victim = os.path.join(self.repo, "doomed.js")
        with open(victim, "w") as f:
            f.write("x\n")
        _run(["git", "add", "doomed.js"], cwd=self.repo)
        _run(["git", "commit", "-qm", "add", "--no-verify"], cwd=self.repo)
        os.remove(victim)
        _run(["git", "add", "-A"], cwd=self.repo)

        p = self._run_hook()
        self.assertEqual(p.returncode, 1, "闸门缺失时必须阻止提交")
        self.assertIn("无法确认", p.stderr)


class InstallerTests(SimpleTestCase):
    """安装脚本：hooksPath 冲突 / 幂等 / 不覆盖别人的 hook / LF 保证。"""

    def setUp(self):
        if not HAS_BASH:
            self.skipTest("本机没有 bash")
        self.tmp = tempfile.mkdtemp(prefix="inst_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        # 只复制安装脚本真正需要的那几个文件。
        # ⚠️ 不要 copytree 整个仓库：venv / node_modules 动辄上万个文件，
        #    复制会极慢，还可能触发沙箱限制（实测整仓复制直接被 SIGTERM）。
        os.makedirs(os.path.join(self.repo, "scripts", "hooks"), exist_ok=True)
        shutil.copy(INSTALLER, os.path.join(self.repo, "scripts",
                                            "install_git_hooks.py"))
        shutil.copy(TEMPLATE, os.path.join(self.repo, "scripts", "hooks",
                                           "pre-commit-capability-guard"))
        _run(["git", "init", "-q"], cwd=self.repo)
        _run(["git", "config", "user.email", "t@t"], cwd=self.repo)
        _run(["git", "config", "user.name", "t"], cwd=self.repo)
        self.installer = os.path.join(self.repo, "scripts", "install_git_hooks.py")

    def _install(self, *args):
        return _run([sys.executable, "-B", self.installer, *args], cwd=self.repo)

    def test_installs_with_lf(self):
        """LF 是硬要求；可执行位在 Windows 上是平台限制（见下一个用例）。"""
        p = self._install()
        self.assertEqual(p.returncode, 0, p.stderr)
        target = os.path.join(self.repo, ".git", "hooks", "pre-commit")
        self.assertTrue(os.path.isfile(target))
        with open(target, "rb") as f:
            raw = f.read()
        self.assertNotIn(b"\r\n", raw, "装出来的 hook 必须是 LF")

    def test_executable_bit_is_honest_about_platform_limits(self):
        """★ 实测的平台事实：**Windows 的 Python 无法设置可执行位**。

        `os.chmod(..., S_IXUSR)` 在 NTFS 上是空操作（stat 出来仍是 0o100666）。
        ⇒ 关键不是"位有没有设上"，而是：
          1. 安装脚本不能因此失败、不能假装成功；
          2. Git for Windows 执行 hook 时**不检查**该位（已实测 hook 能正常跑）。
        Linux/macOS 上则必须真的设上 —— 所以这里按平台分别断言。
        """
        p = self._install()
        target = os.path.join(self.repo, ".git", "hooks", "pre-commit")
        is_exec = bool(os.stat(target).st_mode & stat.S_IXUSR)
        if os.name != "nt":
            self.assertTrue(is_exec, "非 Windows 平台必须真的设上可执行位")
        else:
            # 断言安装脚本如实报告，而不是谎报成功
            self.assertIn("可执行位已设置", p.stdout)
            self.assertIn("False", p.stdout,
                          "Windows 上应如实报告没设上，并说明是平台限制")
            self.assertIn("Git for Windows", p.stdout,
                          "必须说明为什么这不影响使用")

    def test_installed_hook_is_actually_executable_by_git(self):
        """★ 端到端：装出来的 hook 必须真的能被执行（不只是文件存在）。"""
        self._install()
        target = os.path.join(self.repo, ".git", "hooks", "pre-commit")
        # 直接以 hook 解释器跑它，无删除时应秒退 0
        p = _run([BASH, target], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("not found", p.stderr,
                         "hook 跑不起来（常见于 CRLF 的 $'\\r' 问题）")

    def test_install_is_idempotent(self):
        self._install()
        p = self._install()
        self.assertEqual(p.returncode, 0)
        self.assertIn("无需改动", p.stdout)

    def test_hooks_path_conflict_is_detected(self):
        """★ core.hooksPath 被设置时，写 .git/hooks/ 是无效的。

        不检查就装 = 装了个不生效的东西，比不装更糟
        （让人以为有闸门，实际没有）。
        """
        alt = os.path.join(self.repo, "my-hooks")
        os.makedirs(alt, exist_ok=True)
        _run(["git", "config", "core.hooksPath", "my-hooks"], cwd=self.repo)
        p = self._install()
        self.assertEqual(p.returncode, 0, p.stderr)
        # 必须装到 hooksPath 指向的位置，而不是 .git/hooks
        self.assertTrue(os.path.isfile(os.path.join(alt, "pre-commit")),
                        "hooksPath 已设置时必须装到该目录")
        self.assertFalse(
            os.path.isfile(os.path.join(self.repo, ".git", "hooks", "pre-commit")),
            "不该装到 .git/hooks（那里不生效）")

    def test_refuses_to_clobber_foreign_hook(self):
        """★ 已有别人的 hook 时必须拒绝覆盖。"""
        hooks = os.path.join(self.repo, ".git", "hooks")
        os.makedirs(hooks, exist_ok=True)
        target = os.path.join(hooks, "pre-commit")
        with open(target, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n# 我自己写的 hook\necho hi\n")
        p = self._install()
        self.assertEqual(p.returncode, 1, "必须拒绝静默覆盖")
        self.assertIn("拒绝覆盖", p.stdout)
        with open(target, "r", encoding="utf-8") as f:
            self.assertIn("我自己写的 hook", f.read(), "原 hook 被覆盖了")

    def test_force_overwrites(self):
        hooks = os.path.join(self.repo, ".git", "hooks")
        os.makedirs(hooks, exist_ok=True)
        target = os.path.join(hooks, "pre-commit")
        with open(target, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho old\n")
        p = self._install("--force")
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(target, "r", encoding="utf-8") as f:
            self.assertIn("capability-guard", f.read())

    def test_uninstall_refuses_foreign_hook(self):
        hooks = os.path.join(self.repo, ".git", "hooks")
        os.makedirs(hooks, exist_ok=True)
        with open(os.path.join(hooks, "pre-commit"), "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho not ours\n")
        p = self._install("--uninstall")
        self.assertEqual(p.returncode, 1)
        self.assertTrue(os.path.isfile(os.path.join(hooks, "pre-commit")))

    def test_uninstall_removes_our_hook(self):
        self._install()
        p = self._install("--uninstall")
        self.assertEqual(p.returncode, 0)
        self.assertFalse(os.path.isfile(
            os.path.join(self.repo, ".git", "hooks", "pre-commit")))

    def test_status_reports_not_installed(self):
        p = self._install("--status")
        self.assertEqual(p.returncode, 0)
        self.assertIn("未安装", p.stdout)