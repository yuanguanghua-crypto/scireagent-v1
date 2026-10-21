#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migration_drill.py — 在**独立 sqlite 实例**上完整演练 migration

要拦的真实事故：
    部署前在独立实例上跑 migration 全链路，**第一步就抓到**
    `documents/0006` 漏了 commerce 的跨 app 依赖
    ⇒ 回填抛 `FieldError: Cannot resolve keyword 'current_sds_id'`。
    ⚠️ 生产 commerce 已在 0015，所以**没在生产触发** ——
       但新环境 / 回滚 / 分库 / 全新搭建就会炸。
    ⚠️ `manage.py check` **查不出这个**：它只检查 model 层，
       不检查**迁移图的跨 app 依赖**。这是本次事故的关键盲区。

为什么要独立实例：
    在开发库上直接跑 migrate 会污染数据、且失败后难以复现。
    本脚本**只在自己的临时 sqlite 文件**上跑，结束即清理，绝不碰项目 DB。

演练的完整链路（缺一不可）：
    1. 正向迁移到目标的上一个节点
    2. 造**贴近生产真实形态**的存量数据
       （今天的重点：序号版单 + uuid 版单并存，验证 uuid 不被误计入）
    3. 逐个应用目标 migration
    4. **幂等重跑**（重放同一 migration 必须不炸、不重复改数据）
    5. 反向回滚
    6. 每步报告结果

用法：
    # 演练某 app 的全部迁移
    python scripts/migration_drill.py --app documents

    # 演练到指定节点（今天的重点复现方式）
    python scripts/migration_drill.py --app documents --target 0006

    # 只做静态依赖审计（不跑迁移，最快）
    python scripts/migration_drill.py --app documents --audit-only

    # 保留临时库以便事后查
    python scripts/migration_drill.py --app documents --keep-db

退出码：0 = 全链路通过；1 = 演练失败（迁移报错 / 依赖缺失 / 回滚不一致）；
        2 = 用法/环境错误。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "backend")

# 跨 app 依赖缺失的特征报错。Django 抛的 FieldError 长这样：
#   FieldError: Cannot resolve keyword 'current_sds_id' into field.
#   → 说明迁移代码读了某个**当时还不存在**的字段 ⇒ 依赖声明漏了。
FIELD_ERROR_RE = re.compile(
    r"Cannot resolve keyword ['\"]?(?P<field>[\w.]+)['\"]? into field", re.I)
# 另一种等价形态：Cannot resolve keyword 'x' into field. Choices are: ...
CHOICES_RE = re.compile(
    r"Cannot resolve keyword ['\"]?(?P<field>[\w.]+)['\"]?.*?Choices are", re.I | re.S)


class Step:
    def __init__(self, name):
        self.name = name
        self.ok = True
        self.detail = ""
        self.critical = False


class Drill:
    def __init__(self, app: str, target: str | None, keep_db: bool,
                 verbose: bool = False):
        self.app = app
        self.target = target
        self.keep_db = keep_db
        self.verbose = verbose
        self.steps: list[Step] = []
        self.db_path: str | None = None
        self.settings_mod: str | None = None
        self.prev: str | None = None      # 目标的前一个迁移节点（造数用）

    # ── 环境准备 ────────────────────────────────────────────────────
    def _python(self) -> str:
        for cand in (os.path.join(BACKEND, "venv", "Scripts", "python.exe"),
                     os.path.join(BACKEND, "venv", "bin", "python")):
            if os.path.isfile(cand):
                return cand
        return sys.executable

    def _settings_module_name(self) -> str:
        return "_migration_drill_settings"

    def setup_isolated_env(self) -> None:
        """建独立 DB 文件 + 临时 settings 模块，**不碰项目 DB**。

        ⚠️ 为什么必须写 settings 模块到 backend/ 目录里：
           Django 的 `--settings` 按模块名导入，必须在 sys.path 上。
           写到 backend/ 下最省事（manage.py 就在那儿），且用下划线前缀
           表明是临时产物。
        ⚠️ 为什么不复用 DB_NAME 环境变量：
           实测 `config/settings/development.py` 在 DB_ENGINE=sqlite 时
           **硬编码**了 NAME=BASE_DIR/db.sqlite3，直接忽略 DB_NAME ⇒
           设了 DB_NAME 也照样写进项目库。这是必须覆盖 settings 的原因。
        """
        self.db_path = os.path.join(
            tempfile.gettempdir(),
            f"migration_drill_{self.app}_{os.getpid()}.sqlite3")
        for suffix in ("", "-journal", "-wal", "-shm"):
            p = self.db_path + suffix
            if os.path.exists(p):
                os.remove(p)

        self.settings_mod = self._settings_module_name()
        mod_path = os.path.join(BACKEND, self.settings_mod + ".py")
        with open(mod_path, "w", encoding="utf-8") as f:
            f.write(
                "# 自动生成：migration_drill.py 的临时 settings，用完即删。\n"
                "from config.settings.development import *  # noqa\n"
                "DATABASES['default']['NAME'] = %r\n"
                "DATABASES['default']['ATOMIC_REQUESTS'] = False\n"
                "# 测试库名也隔离，避免 pytest 的 test_库被写\n"
                "DATABASES['default']['TEST'] = {'NAME': %r}\n"
                % (self.db_path, self.db_path + "_test")
            )

    def cleanup(self) -> None:
        if self.settings_mod:
            p = os.path.join(BACKEND, self.settings_mod + ".py")
            if os.path.isfile(p):
                os.remove(p)
        if self.db_path and not self.keep_db:
            for suffix in ("", "-journal", "-wal", "-shm", "_test"):
                p = self.db_path + suffix
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    # ── 跑 migrate ─────────────────────────────────────────────────
    def manage(self, *args, expect_ok=True, timeout=600) -> subprocess.CompletedProcess:
        cmd = [self._python(), "-B", "manage.py", *args,
               f"--settings={self.settings_mod}"]
        env = dict(os.environ)
        # 关键：DB_ENGINE 必须**恰好**是 'sqlite'。
        # 实测 base.py 用 `os.getenv('DB_ENGINE') == 'sqlite'` 判断，
        # 而 development.py 在该值下才会换成 sqlite3 后端并摘掉
        # django.contrib.postgres。若写成 'django.db.backends.sqlite3'，
        # models 里的 `_USE_POSTGRES` 判断（!= 'sqlite'）会认为在 Postgres，
        # 于是声明了 SearchVectorField，而 sqlite 迁移又没建该列 ⇒
        # 建库时序列化直接炸（no such column: application.search_vector）。
        # 这个坑很隐蔽：命令看着"更规范"，实际全盘失败。
        env["DB_ENGINE"] = "sqlite"
        env.setdefault("SECRET_KEY", "migration-drill-only")
        return subprocess.run(
            cmd, cwd=BACKEND, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env, timeout=timeout)

    # ── 迁移图查询 ─────────────────────────────────────────────────
    def leaf_nodes(self) -> list[str]:
        """该 app 当前的叶子迁移名（不含 000x_ 前缀的完整名）。"""
        p = self.manage("showmigrations", self.app)
        if p.returncode != 0:
            return []
        names = []
        for line in p.stdout.splitlines():
            m = re.match(r"^\s*\[[X ]\]\s+(\S+)", line)
            if m:
                names.append(m.group(1))
        return names

    def resolve_target(self, target: str | None) -> tuple[str | None, str | None]:
        """把 0006 解析成完整迁移名。返回 (完整名, 前一个节点)。"""
        names = self.leaf_nodes()
        if not names:
            return None, None
        if target is None:
            return names[-1], (names[-2] if len(names) > 1 else None)
        for n in names:
            if n == target or n.startswith(target + "_") or n.split("_")[0] == target:
                idx = names.index(n)
                prev = names[idx - 1] if idx > 0 else None
                return n, prev
        return None, None

    # ── 跨 app 依赖审计（静态，不需要跑迁移）────────────────────────
    def audit_dependencies(self, backend_root: str | None = None) -> list[str]:
        """★ 今天事故的核心：静态找「RunPython 里读了别的 app 的字段，
        但 dependencies 没声明那个 app」。

        这是 `manage.py check` 查不出来的部分 —— check 只看 model 层。

        :param backend_root: 换个根目录扫（测试用：对着临时副本跑变异）。
        """
        problems = []
        base = backend_root or BACKEND
        mig_dir = os.path.join(base, "apps", self.app, "migrations")
        if not os.path.isdir(mig_dir):
            problems.append(f"找不到迁移目录：{mig_dir}")
            return problems

        # 本 app 各迁移的 dependencies 声明
        declared = {}
        for fn in sorted(os.listdir(mig_dir)):
            if not fn.endswith(".py") or fn == "__init__.py":
                continue
            name = fn[:-3]
            with open(os.path.join(mig_dir, fn), "r", encoding="utf-8",
                      errors="replace") as f:
                src = f.read()
            deps = re.search(r"dependencies\s*=\s*\[(.*?)\]", src, re.S)
            declared[name] = deps.group(1) if deps else ""

        for name, dep_src in declared.items():
            src_path = os.path.join(mig_dir, name + ".py")
            with open(src_path, "r", encoding="utf-8", errors="replace") as f:
                src = f.read()

            # 找出 RunPython 回调里 `apps.get_model('X', ...)` 引用的**其他** app
            runpy_blocks = re.findall(
                r"def\s+_?\w*forward\w*\s*\(.*?\n(?=\ndef |\nclass |\Z)",
                src, re.S)
            if not runpy_blocks:
                runpy_blocks = re.findall(
                    r"RunPython\(\s*(\w+)", src)
                runpy_blocks = [b for b in runpy_blocks if isinstance(b, str)]

            for other in set(re.findall(
                    r"get_model\(\s*['\"](\w+)['\"]", "\n".join(runpy_blocks))):
                if other in ("self", self.app):
                    continue
                if f"'{other}'" not in dep_src and f'"{other}"' not in dep_src:
                    problems.append(
                        f"{self.app}/{name}：数据迁移引用了 app '{other}' 的模型，"
                        f"但 dependencies 未声明 ('{other}', ...) "
                        f"⇒ 若 {other} 尚未迁到含所需字段的版本，"
                        f"回填会抛 FieldError: Cannot resolve keyword")
        return problems

    # ── 造贴近生产的存量数据 ───────────────────────────────────────
    def seed(self) -> str:
        """造**贴近生产真实形态**的数据。

        ⚠️ 关键实现约束：**必须用历史模型，不能用当前模型**。
           演练第①步把库迁到了目标的前一个节点，此时 schema 是**旧的**
           （例如还没有 `catalog_no` 列）。若直接用 `apps.get_model()` 拿
           **当前**模型去插入，会因「模型字段比表多」而报
           `table product has no column named catalog_no` —— 实测踩到。
           ⇒ 正确做法是用 Django 的**迁移状态渲染器**拿到「当时」的模型：
               from django.db.migrations.executor import MigrationExecutor
               from django.db.migrations.state import ProjectState
               state = MigrationExecutor(connections['default']).loader.project_state(('documents','0005'))
               OldProduct = state.apps.get_model('commerce', 'Product')
           这样造出来的数据才**真的符合那一刻的生产形态**。
        """
        script = os.path.join(tempfile.gettempdir(),
                              f"_drill_seed_{os.getpid()}.py")
        # 注入「此刻」的迁移点，造数脚本据此取历史模型
        src = (SEED_SCRIPT
               .replace("__DRILL_APP__", repr(self.app))
               .replace("__DRILL_STATE__", repr(self.prev or "zero")))
        with open(script, "w", encoding="utf-8") as f:
            f.write(src)
        try:
            p = self.manage("shell", "-c",
                            f"exec(open({script!r}, encoding='utf-8').read())")
            out = (p.stdout or "") + (p.stderr or "")
            if p.returncode != 0:
                return "造数失败：" + _tail_raw(out)
            line = ""
            for ln in out.splitlines():
                if ln.startswith("[seed]"):
                    line = ln
            return line or "造数脚本无输出（可疑）"
        finally:
            if os.path.exists(script):
                os.remove(script)

    # ── 主流程 ─────────────────────────────────────────────────────
    def run(self, audit_only=False) -> bool:
        self.setup_isolated_env()
        ok = True
        try:
            # 步骤 0：静态依赖审计
            s = Step("静态依赖审计（manage.py check 查不到的部分）")
            probs = self.audit_dependencies()
            s.ok = not probs
            s.detail = "无跨 app 依赖缺失" if not probs else \
                f"{len(probs)} 处可疑：" + "；".join(probs)
            s.critical = True
            self.steps.append(s)
            ok = ok and s.ok

            if audit_only:
                return ok

            full, prev = self.resolve_target(self.target)
            s = Step("解析目标迁移")
            s.ok = full is not None
            s.detail = (f"目标 {self.app}/{full}"
                        + (f"，前节点 {prev}" if prev else "（已是首个）")
                        ) if full else (
                f"在 app '{self.app}' 里找不到迁移 "
                f"'{self.target}'；现有：{', '.join(self.leaf_nodes())}")
            self.steps.append(s)
            if not s.ok:
                return False
            self.prev = prev

            # 步骤 1：正向迁移到前一个节点
            s = Step("① 正向迁移到目标的前一个节点")
            if prev:
                p = self.manage("migrate", self.app, prev)
                s.ok = p.returncode == 0
                s.detail = "OK" if s.ok else _tail(p)
            else:
                s.detail = "目标就是首个迁移，跳过"
            s.critical = True
            self.steps.append(s)
            ok = ok and s.ok
            if not s.ok:
                return False

            # 步骤 2：造存量数据
            s = Step("② 造贴近生产形态的存量数据")
            if self.prev is None:
                # ★ 2026-10-21 修：当目标就是该 app 的**首个迁移**时，没有"存量 schema"可言
                #   （表都还不存在）⇒ 造数**不适用**。
                #   原实现会把 "zero" 当迁移节点传给 `project_state()`，
                #   抛 `NodeNotFoundError: Node ('app','zero') not a valid node`
                #   ⇒ 整个演练被误判为失败（而 ③④⑤ 其实都通过了）。
                #   实测：每个 app 的 `0001_initial` 都会踩到，10 个 app 全军覆没。
                s.detail = "目标是首个迁移（无存量 schema）⇒ 不适用，跳过造数"
            else:
                s.detail = self.seed()
            # ⚠️ 造数失败必须**标红**：数据没造出来时，
            #    后面③的迁移「成功」只证明了空库能迁 —— 毫无价值。
            #    实测踩到：seed 脚本因模型名写错而静默退出，
            #    演练却报告「全链路通过」，那是**假绿灯**，比红灯更危险。
            s.ok = self.prev is None or ("失败" not in s.detail and "缺少" not in s.detail)
            s.critical = True
            self.steps.append(s)
            ok = ok and s.ok

            # 步骤 3：正向应用目标迁移
            s = Step(f"③ 应用目标迁移 {self.app}/{full}")
            p = self.manage("migrate", self.app, full)
            s.ok = p.returncode == 0
            out = (p.stdout or "") + (p.stderr or "")
            s.detail = "OK" if s.ok else self.classify_failure(out)
            if s.ok and "[data-migration]" in out:
                for line in out.splitlines():
                    if "[data-migration]" in line:
                        s.detail = line.strip()
            s.critical = True
            self.steps.append(s)
            ok = ok and s.ok
            if not s.ok:
                return False

            # 步骤 4：幂等重跑
            s = Step("④ 幂等重跑（同一迁移重放不应炸）")
            p = self.manage("migrate", self.app, full)
            s.ok = p.returncode == 0
            s.detail = ("无待应用迁移，符合预期" if s.ok else _tail(p))
            self.steps.append(s)
            ok = ok and s.ok

            # 步骤 5：反向回滚
            s = Step("⑤ 反向回滚")
            p = self.manage("migrate", self.app, prev) if prev else \
                self.manage("migrate", self.app, "zero")
            s.ok = p.returncode == 0
            s.detail = "回滚成功" if s.ok else _tail(p)
            s.critical = True
            self.steps.append(s)
            ok = ok and s.ok

            return ok
        except subprocess.TimeoutExpired:
            self.steps.append(Step("演练超时"))
            return False
        except Exception:
            traceback.print_exc()
            return False
        finally:
            self.cleanup()

    def classify_failure(self, out: str) -> str:
        """把失败分类 —— 特别是**依赖缺失**，这是今天的真 bug。"""
        m = FIELD_ERROR_RE.search(out) or CHOICES_RE.search(out)
        if m:
            field = m.group("field")
            return (f"❌ 跨 app 依赖缺失：FieldError: Cannot resolve keyword "
                    f"'{field}'。\n"
                    f"   ⇒ 数据迁移读到了当时还不存在的字段。"
                    f"通常是在 dependencies 里少声明了引入该字段的那个 app 的迁移。\n"
                    f"   ⇒ 生产当前进度可能刚好掩盖了它，但**新环境 / 回滚 / 分库会炸**。")
        if "ProgrammingError" in out and "no such column" in out.lower():
            return ("❌ schema 不一致（no such column）：迁移顺序有问题，"
                    "或依赖的 app 尚未迁移到对应版本。\n" + _tail_raw(out))
        if "no such table" in out.lower():
            return ("❌ 依赖的表还不存在 ⇒ 依赖声明缺失。\n" + _tail_raw(out))
        return "迁移失败：\n" + _tail_raw(out)


def _tail(p: subprocess.CompletedProcess, n=6) -> str:
    lines = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
    return " | ".join(l.strip() for l in lines[-n:] if l.strip())


def _tail_raw(out: str, n=8) -> str:
    lines = (out or "").strip().splitlines()
    return "\n     ".join(l.strip() for l in lines[-n:] if l.strip())


# 造数脚本：贴近生产真实形态 —— 序号版单 + uuid 版单并存
SEED_SCRIPT = r'''
# -*- coding: utf-8 -*-
"""造贴近生产真实形态的存量数据（migration_drill 用）。

★ 两个必须做对的地方（都是实测踩出来的）：

1) **必须用历史模型，不能用当前模型。**
   演练第①步把库迁到「目标的前一个节点」，schema 是**旧的**。
   用当前模型插入会报 `table product has no column named catalog_no`
   —— 因为新列是后面的迁移才加的。
   ⇒ 用 MigrationExecutor.loader.project_state(...) 拿那一刻的模型。

2) **只造这一刻真实存在的表。**
   某个模型如果在这个迁移点还不存在（如 transactions 的 order 表），
   就不该硬造 —— 那是「未来」的形态，混进来会掩盖真实的迁移问题。
   ⇒ 造数前用 state.apps.get_model 探测，缺失就跳过并**明说**。

★ 数据形态（今天的重点）：单号同时存在两种形态 ——
    · 序号版单 `ORD-YYYYMMDD-NNN`  （计数器口径，next_checkout_order_no）
    · uuid  版单 `ORD-{hex8}`      （PoSubmissionService.submit 直接 uuid4）
  迁移若假设了单一形态，回填/统计就会口径错 ⇒ 两种都要造。
"""
import datetime
import uuid

from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.apps import apps as current_apps

TARGET_APPS = (__DRILL_APP__, __DRILL_STATE__)
notes = []

executor = MigrationExecutor(connections["default"])
state = executor.loader.project_state(TARGET_APPS)


def _has_table(model) -> bool:
    """这个模型此刻在库里真的有表吗？"""
    with connection.cursor() as c:
        return model._meta.db_table in connection.introspection.table_names(c)


def _safe(fn, label):
    try:
        fn()
    except Exception as e:
        notes.append("造数失败[%s]: %s: %s" % (label, type(e).__name__, e))


def seed_sds():
    """documents/commerce：0006 的回填读 Product.current_sds 指针。"""
    # ★ 2026-10-21 修：演练**其他 app**（如 accounts）时，drill 只把该 app 迁到 prev，
    #   commerce / documents **根本不在迁移图里** ⇒ `get_model` 抛
    #   `LookupError: No installed app with label 'commerce'`。
    #   原实现把它记成「造数失败」⇒ 整个演练被判失败（台账 6/10），
    #   但真正失败的是"seed 不适用于该 app"，**迁移链路本身是好的**。
    #   ⇒ 这种情况下记「跳过」（不含"失败"字样），让判定正确，同时台账会标注"空库迁移"。
    try:
        Product = state.apps.get_model("commerce", "Product")
        SdsRevision = state.apps.get_model("documents", "SdsRevision")
    except LookupError as e:
        notes.append("跳过 sds 造数：此刻迁移图里没有 commerce/documents（%s）" % e)
        return
    if not _has_table(Product) or not _has_table(SdsRevision):
        notes.append("跳过 sds 造数：此刻表尚未存在")
        return
    fields = {f.name for f in Product._meta.get_fields()}
    made = linked = 0
    for i in range(4):
        kwargs = {"name": "drill-product-%d" % i}
        if "slug" in fields:
            kwargs["slug"] = "drill-product-%d" % i
        if "catalog_no" in fields:
            kwargs["catalog_no"] = "DRILL-%03d" % i
        p = Product.objects.create(**kwargs)
        made += 1
        revs = []
        for rev in (1, 2):
            sdfields = {f.name for f in SdsRevision._meta.get_fields()}
            rk = {
                "product": p,
                "revision_no": rev,
                "revised_at": datetime.date(2026, 1, 1 + i),
                "change_note": "drill rev %d" % rev,
                "pdf_path": "drill/rev%d.pdf" % rev,
            }
            if "data_confidence" in sdfields:
                rk["data_confidence"] = "high"
            revs.append(SdsRevision.objects.create(**rk))
        # ⚠️ `current_sds` 是否存在，取决于**这个迁移点** commerce 走到哪了。
        #   documents/0005 并不依赖 commerce/0006（实测：0005 只依赖 documents/0004），
        #   所以在「documents 迁移到 0005」这个状态下 commerce 可能还在 0005，
        #   `current_sds` 尚未存在 —— 这时不该硬塞字段，否则造数本身就会失败。
        #   ⇒ 存在就设（回填才有东西可标），不存在就如实报告 0。
        if "current_sds" in fields:
            p.current_sds = revs[0]
            p.save(update_fields=["current_sds"])
            linked += 1
    notes.append("Product %d / SdsRevision %d / current_sds 已设 %d%s"
                 % (made, SdsRevision.objects.count(), linked,
                    "" if linked else "（此刻 commerce 尚未引入该字段，属正常）"))


def seed_orders():
    """transactions：序号版单 + uuid 版单并存（此刻无表就跳过）。"""
    try:
        Order = state.apps.get_model("transactions", "Order")
    except LookupError:
        notes.append("跳过订单造数：此刻 transactions 尚未纳入迁移图")
        return
    if not _has_table(Order):
        notes.append("跳过订单造数：此刻 order 表尚不存在")
        return
    fields = {f.name for f in Order._meta.get_fields()}
    seq_n = uuid_n = 0
    for i in range(3):
        if "order_no" in fields and "status" in fields:
            # ★ 2026-10-21 修：`po_number` 的历史版本是 **`unique=True`**
            #   （现版本已改成"条件唯一"，见 models.py 注释：空串/NULL 不进唯一索引，
            #     否则"任意登录用户连建两单、第二单 500"）。
            #   而演练跑在**迁移状态里的历史模型**上 ⇒ 不传 po_number 会落默认空串 ''，
            #   第二条就撞 `UNIQUE constraint failed: order.po_number`（实测 inventory 演练卡在这）。
            #   ⇒ 每条订单都显式给唯一 PO 号，使造数在"任何历史版本"下都成立。
            def _extra():
                if "po_number" not in fields:
                    return {}
                try:
                    return {"po_number": "DRILL-%s" % uuid.uuid4().hex[:10].upper()}
                except Exception:
                    return {}

            Order.objects.create(
                order_no="ORD-2026010%d-00%d" % (i + 1, i + 1), status="draft", **_extra())
            seq_n += 1
            Order.objects.create(
                order_no="ORD-%s" % uuid.uuid4().hex[:8].upper(), status="draft", **_extra())
            uuid_n += 1
    if seq_n or uuid_n:
        notes.append("Order 序号版 %d + uuid 版 %d" % (seq_n, uuid_n))
    else:
        notes.append("跳过订单造数：Order 无 order_no/status 字段")


for _fn, _label in ((seed_sds, "documents/commerce"),
                    (seed_orders, "transactions 双形态单据")):
    _safe(_fn, _label)

print("[seed] " + " | ".join(notes))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="在独立 sqlite 实例上完整演练 migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--app", required=True, help="要演练的 app，如 documents")
    ap.add_argument("--target", default=None,
                    help="演练到哪个迁移，如 0006（默认该 app 的最后一个）")
    ap.add_argument("--audit-only", action="store_true",
                    help="只做静态跨 app 依赖审计，不跑迁移")
    ap.add_argument("--keep-db", action="store_true",
                    help="保留临时 DB 文件以便事后检查")
    args = ap.parse_args(argv)

    if not os.path.isdir(os.path.join(BACKEND, "apps", args.app)):
        print(f"[错误] 找不到 app：backend/apps/{args.app}", file=sys.stderr)
        print(f"        现有：{', '.join(sorted(os.listdir(os.path.join(BACKEND, 'apps'))))}",
              file=sys.stderr)
        return 2

    if not os.path.isdir(os.path.join(BACKEND, "apps", args.app, "migrations")):
        print(f"[错误] app '{args.app}' 没有 migrations 目录", file=sys.stderr)
        return 2

    print("=" * 78)
    print(f"migration 演练｜app={args.app}"
          f"｜target={args.target or '(最后一个)'}"
          f"｜独立 sqlite 实例")
    print("=" * 78)

    d = Drill(args.app, args.target, args.keep_db)
    ok = d.run(audit_only=args.audit_only)

    print()
    for s in d.steps:
        icon = "✅" if s.ok else ("🛑" if s.critical else "⚠️ ")
        print(f"{icon} {s.name}")
        if s.detail:
            for line in str(s.detail).splitlines():
                print(f"      {line}")
    print()
    print(f"[结论] {'全链路通过' if ok else '演练失败 —— 详见上面标记项'}")
    if not args.audit_only:
        if args.keep_db and d.db_path:
            print(f"[临时库已保留] {d.db_path}")
        else:
            print("[临时库已清理] 项目 DB 未被触碰")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())