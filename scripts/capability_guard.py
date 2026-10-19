#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capability_guard.py — 删除前「能力入口丢失」闸门 + 能力地图

要拦的错误（真实发生过的形态）：
    一个前端文件「零路由注册 + 零 import 引用」→ 被判定为死代码删掉
    → 但它其实是某个**后端存活端点**或**后端存活写入字段**的唯一前端入口
    → 「零引用」被误当成「无能力」，能力从此没有 UI。

设计要点（为什么这么写，见 --help 的长说明）：
  1. 后端端点用 Django/DRF 真实注册语义提取（path() + router.register() + @action），
     而不是文件名/URL 字符串 grep —— grep 看不见 router 展开的 detail 路由。
  2. 前端调用方用 import 语句解析（@ 别名 / 相对路径 / 命名空间 / 动态 import），
     而不是文件名 grep —— `.js` 的文件名根本不出现在 import 语句里。
  3. api 层内部的符号依赖做**传递闭包**：api/a.js 调 api/b.js 的 getX，
     而 a.js 只被待删文件引用 ⇒ getX 的入口同样会随删除消失。
     ⇒ 「调用方」只认**非 api 层文件**（views/components/stores…），
       api 层是定义处不是入口处。
  4. 双重判定：
       L1 端点级  —— 唯一调用方 + 后端路由存活 (+测试)  ⇒ BLOCK
       L2 字段级  —— serializer 声明存活 + 全前端唯一「写入方」 ⇒ BLOCK
     L2 是必要的：现役页面可以「取了数据但不提交字段」，
     端点级检查完全看不见这种「能力已失去写入入口」的情况。

用法：
    python scripts/capability_guard.py --map
        打印「后端存活端点 → 前端调用方」映射表，标出零调用方的孤儿能力。

    python scripts/capability_guard.py --check frontend/src/views/admin/Foo.vue
        删除前预演：该文件若被删除，哪些能力会失去唯一入口。

    python scripts/capability_guard.py --audit --git-rev 5868600^ \\
        --paths frontend/src/views/admin/AdminProductsPage.vue \\
                 frontend/src/views/admin/AdminProductEdit.vue
        事后审计：文件已从磁盘消失，用 git 取回内容按「待删」处理。

    --out FILE       把输出写入文件（--map 时默认写 deliverables/capability_map.txt）
    --json           机器可读输出（接 CI / pre-commit）
    --force          有 BLOCK 也退出 0（仅供人工研判时用，不要接 CI）

退出码：0 = OK，1 = BLOCK，2 = 用法/环境错误。
"""
from __future__ import annotations

import argparse
import ast
import difflib
import io
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── 容器/常量 ──────────────────────────────────────────────────────────
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "backend")
FRONTEND_SRC = os.path.join(REPO, "frontend", "src")
API_DIR = os.path.join(FRONTEND_SRC, "api")

SKIP_DIRS = {"node_modules", "venv", "__pycache__", ".git", "dist", "_audit_tmp",
             "_lead_stash", "e2e", "knowledge_packs", "deliverables"}

API_PREFIX = "/api/v1"          # axios baseURL（frontend/src/utils/http.js）
TEST_ROOT_RELPATHS = ["apps"]   # 只在 apps/ 下找测试

# 前端可能出现的 HTTP 客户端形态
HTTP_VERBS = ("get", "post", "put", "patch", "delete")

# 判定「字段写入」时认可的对象容器名（H1 规则）
WRITE_CONTAINERS = {
    "payload", "form", "formData", "body", "data", "fields", "request", "req",
    "params", "updateData", "postData", "bodyData", "attrs", "detail",
}

SOURCE_EXT = (".vue", ".js", ".ts", ".jsx", ".tsx")


# ── 小工具 ────────────────────────────────────────────────────────────
def rel(path: str) -> str:
    """绝对路径 → 仓库相对路径（统一正斜杠）。"""
    return os.path.relpath(path, REPO).replace("\\", "/")


def apath(path: str) -> str:
    """绝对路径 → **统一正斜杠**的绝对路径（索引键的唯一规范形态）。

    ⚠️ 这不是洁癖，是 P0 漏洞的根因：`scan_api_layer` 走 `os.walk(API_DIR)`，
    在 Windows 上 os.path.join 产出**反斜杠**键（`C:\\...\\api\\documents.js`）；
    而 `resolve_spec` 内部 `.replace("\\\\","/")` 产出**正斜杠**
    （`C:/.../api/documents.js`）。两者字符串不等，于是
    `self.exports.get(target)` 恒得空集 —— 命名空间导入与
    `export {a} from './b'` 转发**静默失效**，删除闸门因此漏放行。
    统一成正斜杠后，跨平台（Windows/POSIX）都命中同一把键。
    """
    return os.path.abspath(path).replace("\\", "/")


def _emit(text: str, out_path: str | None) -> None:
    """输出到 stdout；若给了 out_path 则同时落盘（自动建目录）。"""
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[已写入] {rel(out_path)}")
    else:
        print(text, end="" if text.endswith("\n") else "\n")


# 每次运行都会变的内容（耗时/时间戳）—— 必须在对比前抹掉，否则生成物永远"不一致"
_VOLATILE_LINE = re.compile(r"^\[耗时\].*$", re.M)


def strip_volatile(text: str) -> str:
    """把生成物里每次运行都会变的行归一化，使其可用于逐行对比。"""
    return _VOLATILE_LINE.sub("[耗时] <不参与对比>", text)


def diff_map_text(actual: str, fresh: str) -> list[str]:
    """对比「已提交的映射表」与「按当前代码重新生成的」，返回 unified diff。

    ★ 纯函数（不依赖索引构建）⇒ 可被单元测试直接覆盖。
    ★ 两边都先 `strip_volatile`：否则每次运行不同的 `[耗时]` 行
      会让「内容完全相同」的两份也被判为不一致。
    """
    return list(difflib.unified_diff(
        strip_volatile(actual).splitlines(),
        strip_volatile(fresh).splitlines(),
        fromfile="已提交", tofile="按当前代码重新生成",
        lineterm="", n=0,
    ))


def render_map_text(m, be, fe, verbose: bool, t_index: float, t_total: float) -> str:
    """把映射表渲染成完整文本。

    ★ 为什么抽成函数：`--map`（落盘）与 `--verify-map`（与已提交文件对比）
      必须用**同一段渲染逻辑**，否则对比本身就不可信。
    """
    buf = io.StringIO()
    real = sys.stdout
    sys.stdout = buf                      # print_map 内部用 print，需要重定向
    try:
        print_map(m, verbose)
        print(f"\n[耗时] 索引构建 {t_index:.2f}s｜总计 {t_total:.2f}s"
              f"｜后端端点 {len(be.routes())}｜api 符号 {len(fe.symbols)}")
    finally:
        sys.stdout = real
    return buf.getvalue()


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def git_show(rev: str, path: str) -> str | None:
    """从 git 取回某个 rev 下的文件内容（用于事后审计已删文件）。"""
    try:
        out = subprocess.run(
            ["git", "-C", REPO, "show", f"{rev}:{path}"],
            capture_output=True, timeout=30,
        )
        if out.returncode == 0:
            return out.stdout.decode("utf-8", errors="replace")
    except Exception:
        pass
    return None


def iter_source_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(SOURCE_EXT):
                yield os.path.join(dirpath, fn)


def match_paren(text: str, open_idx: int) -> int:
    """给定 '(' 的下标，返回配对 ')' 的下标；找不到返回 -1。会跳过字符串/模板串。"""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "'\"`":
            quote = ch
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def match_brace(text: str, open_idx: int) -> int:
    """给定 '{' 的下标，返回配对 '}' 的下标。"""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "'\"`":
            quote = ch
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def norm_path(p: str) -> str:
    """把 Django path / DRF router path / 前端模板串归一到同一坐标系。

    <int:pk>  {pk}  ${productId}   →   {X}
    """
    if p is None:
        return ""
    p = p.strip()
    p = re.sub(r"<(?:int|str|slug|uuid|path):[^>]+>", "{X}", p)   # Django converter
    p = re.sub(r"<(?:int|str|slug|uuid|path)>", "{X}", p)
    p = re.sub(r"\{[^}]+\}", "{X}", p)                              # DRF router
    p = re.sub(r"\$\{[^}]*\}", "{X}", p)                           # JS 模板串
    p = p.split("?")[0]
    if not p.startswith("/"):
        p = "/" + p
    p = re.sub(r"/{2,}", "/", p)
    return p


def full_url(frag: str) -> str:
    """把路由片段补成含 /api/v1 前缀的完整 URL（前端 baseURL 同前缀）。"""
    frag = norm_path(frag)
    if not frag.startswith("/"):
        frag = "/" + frag
    if frag.startswith(API_PREFIX):
        return frag
    return API_PREFIX + frag


def path_to_regex(p: str) -> re.Pattern:
    """归一路径 → 匹配正则（{X} 匹配一段非斜杠）。"""
    parts = []
    for seg in p.split("/"):
        parts.append("[^/]+" if seg == "{X}" else re.escape(seg))
    return re.compile("^" + "/".join(parts) + "$")


# ══════════════════════════════════════════════════════════════════════
# 1. 后端端点索引
# ══════════════════════════════════════════════════════════════════════
class Endpoint:
    __slots__ = ("method", "path", "view", "source", "line", "kind")

    def __init__(self, method, path, view, source, line, kind="path"):
        self.method = method          # GET/POST/... 或 "*"（router 列表）
        self.path = path              # 归一后的完整 URL
        self.view = view
        self.source = source          # 声明位置（用于人工核对）
        self.line = line
        self.kind = kind              # path / router / action

    @property
    def key(self) -> str:
        return f"{self.method} {self.path}"

    def __repr__(self):
        return f"<Endpoint {self.method} {self.path} @ {rel(self.source)}:{self.line}>"


def _call_name(node: ast.AST) -> str | None:
    """取 `A.b.c(...)` / `f(...)` 的最后一段名字。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _view_symbol(node: ast.AST) -> str:
    """`FooView.as_view()` → 'FooView'；`dashboard_view` → 'dashboard_view'；
    `basket_views.BasketView.as_view()` → 'BasketView'（记录所属模块）。"""
    if isinstance(node, ast.Attribute) and node.attr == "as_view":
        return _call_name(node.value) or "<anonymous>"
    if isinstance(node, ast.Call):
        return _view_symbol(node.func)
    return _call_name(node) or "<anonymous>"


def _view_module(node: ast.AST) -> str | None:
    """`basket_views.BasketView` → 'basket_views'（用于在 urls.py 内二次定位）。"""
    if isinstance(node, ast.Attribute) and node.attr == "as_view":
        v = node.value
        if isinstance(v, ast.Attribute):
            return _call_name(v.value)
    if isinstance(node, ast.Call):
        return _view_module(node.func)
    if isinstance(node, ast.Attribute):
        return _call_name(node.value)
    return None


class ViewActionScanner:
    """扫 views.py，抽出每个 ViewSet 类上的 @action（url_path + detail + methods）。

    没有这一步，router.register('products', ProductViewSet) 只会展开出
    list/detail，archive / hard-delete / generate-seo 这类端点会整片丢失。
    """

    def __init__(self):
        self.actions: dict[str, list[dict]] = {}   # ViewSet 名 → [{url_path, detail, methods}]
        self.files: dict[str, str] = {}            # ViewSet 名 → 声明文件

    def scan_file(self, path: str) -> None:
        try:
            tree = ast.parse(read(path), filename=path)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            acts = []
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for dec in item.decorator_list:
                    if not isinstance(dec, ast.Call):
                        continue
                    if _call_name(dec.func) != "action":
                        continue
                    kw = {k.arg: k.value for k in dec.keywords if k.arg}
                    url_path = None
                    if "url_path" in kw and isinstance(kw["url_path"], ast.Constant):
                        url_path = kw["url_path"].value
                    if url_path is None:
                        url_path = item.name.replace("_", "-")
                    detail = False
                    if "detail" in kw:
                        detail = bool(getattr(kw["detail"], "value", False))
                    methods = ["GET"]
                    if "methods" in kw and isinstance(kw["methods"], (ast.List, ast.Tuple)):
                        got = [e.value for e in kw["methods"].elts
                               if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                        if got:
                            methods = [m.upper() for m in got]
                    acts.append({"url_path": url_path, "detail": detail,
                                 "methods": methods, "func": item.name,
                                 "line": item.lineno})
            if acts:
                self.actions[node.name] = acts
                self.files.setdefault(node.name, path)


class BackendIndex:
    """按 Django 真实注册语义提取全部存活端点。"""

    def __init__(self):
        self.endpoints: list[Endpoint] = []
        self.actions = ViewActionScanner()
        self._scanned_views: set[str] = set()
        self.test_blob = self._load_tests()

    # ── 测试语料（判断端点是否「有测试」）──
    def _load_tests(self) -> str:
        buf = []
        root = os.path.join(BACKEND, "apps")
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                low = fn.lower()
                if not (low.startswith("test") or "/tests/" in dirpath.replace("\\", "/")):
                    continue
                if not fn.endswith(".py"):
                    continue
                buf.append(read(os.path.join(dirpath, fn)))
        return "\n".join(buf)

    def has_test(self, path: str) -> tuple[bool, str]:
        """端点是否有测试覆盖（启发式 H-TEST）。

        收紧要点：router 展开出的 `/products/{X}/` 若按「静态片段子串」判，
        碎片只剩 `/products/` 和 `/`，几乎必然命中 ⇒ 191/216 的假覆盖。
        所以：
          · 静态端点（无 {X}）→ 子串搜，但要求**整条路径**（含 /api/v1 前缀）
            在测试里以字符串出现；
          · 动态端点（含 {X}）→ 把 {X} 放宽成 [^"'`]+ 后，要求命中的是
            **带引号的完整 URL 字面量**，且整条 URL（而非碎片）能对上。
        """
        full = path if path.startswith(API_PREFIX) else API_PREFIX + path
        if "{X}" not in full:
            if full in self.test_blob:
                return True, f"完整路径命中测试：{full}"
            # 测试里也常写相对形式（reverse 断言），退一步用去掉前缀的整条路径
            bare = full[len(API_PREFIX):]
            if bare and bare in self.test_blob:
                return True, f"路径命中测试：{bare}"
            return False, ""

        segs = full.split("/")
        pattern = "/".join("[^\"'`]+" if s == "{X}" else re.escape(s) for s in segs)
        rx = re.compile(rf"[\"'`]({pattern})[\"'`]")
        for m in rx.finditer(self.test_blob):
            return True, f"动态 URL 命中测试：{m.group(1)[:80]}"
        return False, ""

    # ── urls.py 解析 ──
    def _scan_viewset(self, viewset_name: str, hint_file: str | None):
        """确保 ViewSet 的 @action 已被扫描。"""
        if viewset_name in self._scanned_views:
            return
        self._scanned_views.add(viewset_name)
        cands = []
        if hint_file:
            cands.append(hint_file)
        for dirpath, dirnames, filenames in os.walk(os.path.join(BACKEND, "apps")):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".py"):
                    cands.append(os.path.join(dirpath, fn))
        for c in cands:
            if viewset_name in read(c) or (viewset_name in self.actions.files
                                           and self.actions.files[viewset_name] == c):
                self.actions.scan_file(c)

    def scan_urls(self, urls_path: str, prefix: str, _depth: int = 0) -> None:
        if _depth > 4:
            return
        try:
            tree = ast.parse(read(urls_path), filename=urls_path)
        except (SyntaxError, FileNotFoundError):
            return

        # router.register(prefix, ViewSet, basename=...)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node.func) == "register":
                args = node.args
                if len(args) < 2:
                    continue
                if not (isinstance(args[0], ast.Constant) and isinstance(args[0].value, str)):
                    continue
                rprefix = args[0].value.strip("/")
                viewset = _call_name(args[1])
                if not viewset:
                    continue
                self._emit_router(prefix, rprefix, viewset, urls_path, node.lineno)

            # path(route, view, name=...)
            if isinstance(node, ast.Call) and _call_name(node.func) == "path":
                args = node.args
                if len(args) < 2:
                    continue
                if not (isinstance(args[0], ast.Constant) and isinstance(args[0].value, str)):
                    continue
                route = args[0].value
                view = _view_symbol(args[1])
                self.endpoints.append(Endpoint(
                    method="ANY", path=full_url(prefix + "/" + route),
                    view=view, source=urls_path, line=node.lineno, kind="path"))

            # include('apps.x.api.v1.urls')  → 递归
            if isinstance(node, ast.Call) and _call_name(node.func) == "include":
                for a in node.args:
                    target = a.value if isinstance(a, ast.Constant) else None
                    if isinstance(target, str) and "urls" in target:
                        mod_path = os.path.join(BACKEND, *target.split(".")) + ".py"
                        self.scan_urls(mod_path, prefix, _depth + 1)

    def _emit_router(self, prefix, rprefix, viewset, urls_path, line):
        """展开 DefaultRouter：list + detail + @action。"""
        base = prefix + "/" + rprefix
        self.endpoints.append(Endpoint("GET", full_url(base + "/"), viewset,
                                      urls_path, line, "router-list"))
        self.endpoints.append(Endpoint("POST", full_url(base + "/"), viewset,
                                      urls_path, line, "router-list"))
        self.endpoints.append(Endpoint("GET", full_url(base + "/{X}/"), viewset,
                                      urls_path, line, "router-detail"))
        for m in ("PUT", "PATCH", "DELETE"):
            self.endpoints.append(Endpoint(m, full_url(base + "/{X}/"), viewset,
                                          urls_path, line, "router-detail"))
        self._scan_viewset(viewset, None)
        for act in self.actions.actions.get(viewset, []):
            if act["detail"]:
                p = base + "/{X}/" + act["url_path"]
            else:
                p = base + "/" + act["url_path"]
            for m in act["methods"]:
                self.endpoints.append(Endpoint(m, full_url(p), viewset,
                                              self.actions.files.get(viewset, urls_path),
                                              act["line"], "action"))

    def build(self) -> "BackendIndex":
        self.scan_urls(os.path.join(BACKEND, "config", "urls.py"), "")
        return self

    def match(self, http_verb: str, url_path: str) -> Endpoint | None:
        """在前端路径上匹配后端端点。

        尾斜杠容差：前端常写 `/products/${id}`，DRF router 注册的是 `/products/{pk}/`。
        verb 必须真的对得上 —— 否则 `PUT /products/{id}` 会错配到
        `POST /products/batch-restore`（静态段恰好也能被 `{X}` 吃掉），
        凭空造出「唯一入口丢失」的假阻断。

        ⚠️ 动词匹配曾写成 `verb in (e.method, "ANY")`，那判断的是「verb 等于字面量
        "ANY"」。正确语义是「`path()` 注册的端点不声明方法（method='ANY'）⇒ 接受任何
        verb」。这个 bug 被旧的 `(exact or hits)` 兜底掩盖过。

        ⚠️ 更隐蔽的一层：ANY 端点会**吞掉**精确动词匹配。
        `updateProduct` 的 `PUT /products/${id}` 展开成 `/products/{X}/`，
        这个正则同样能匹配 `/products/batch-validate/`；若 ANY 优先，
        批量端点就会被错误归因成「经 updateProduct 调用」。
        所以必须**先取 verb 精确命中，取不到才回退 ANY**。
        """
        target = full_url(url_path)
        verb = (http_verb or "").upper()
        cands = [target]
        if target.endswith("/"):
            cands.append(target[:-1])
        else:
            cands.append(target + "/")
        for cand in cands:
            rx = path_to_regex(cand)
            hits = [e for e in self.endpoints if rx.match(e.path)]
            if not hits:
                continue
            # 静态路由优先于含变量的（与 Django urlpatterns 的顺序语义一致）
            hits.sort(key=lambda e: (e.path.count("{X}"), e.kind != "path"))
            precise = [e for e in hits if verb == e.method]
            if precise:
                return precise[0]
            loose = [e for e in hits if e.method == "ANY"]
            if loose:
                return loose[0]
            # verb 对不上 ⇒ 这条 URL 根本没打在这个端点上，不算命中
        return None

    def routes(self) -> list[Endpoint]:
        seen, out = set(), []
        for e in self.endpoints:
            if e.key not in seen:
                seen.add(e.key)
                out.append(e)
        out.sort(key=lambda e: e.path)
        return out


# ══════════════════════════════════════════════════════════════════════
# 2. 前端索引：api 符号 → 端点；符号 → 入口调用方（非 api 层）
# ══════════════════════════════════════════════════════════════════════
EXPORT_FN = re.compile(r"^export\s+(?:async\s+)?function\s+(\w+)", re.M)
EXPORT_CONST = re.compile(r"^export\s+const\s+(\w+)\s*=", re.M)
EXPORT_LIST = re.compile(r"^export\s*\{([^}]*)\}", re.M)
EXPORT_AS = re.compile(r"^export\s*\*\s*as\s+(\w+)\s+from\s*['\"]([^'\"]+)['\"]", re.M)
EXPORT_FROM = re.compile(r"^export\s*(?:\*|\{[^}]*\})\s*from\s*['\"]([^'\"]+)['\"]", re.M)
IMPORT_STMT = re.compile(
    r"""import\s+(?P<clause>[^'"]*?)\s*from\s*['"](?P<spec>[^'"]+)['"]""", re.S)
IMPORT_DYNAMIC = re.compile(r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""")
BARE_IMPORT = re.compile(r"""^\s*import\s*['"]([^'"]+)['"]""", re.M)

# http 调用：`http.get('/x')` / `http.post(`/x/${id}/`)` / `axios.get` / `fetch('/x')`
HTTP_CALL = re.compile(
    r"""\b(?:http|axios|api|client|request)\s*\.\s*(get|post|put|patch|delete)\s*(?:<[^>]*>)?\s*\(\s*"""
    r"""(?P<q>['"`])(?P<path>[^'"`]*)(?P=q)""")
FETCH_CALL = re.compile(
    r"""\bfetch\s*\(\s*(?P<q>['"`])(?P<path>[^'"`]*)(?P=q)""")


class ApiSymbol:
    __slots__ = ("module", "name", "http", "path", "line", "calls")

    def __init__(self, module, name, http, path, line):
        self.module = module          # api 文件绝对路径
        self.name = name
        self.http = http              # get/post/... 或 None
        self.path = path              # 命中的 URL 片段（可能含 ${}）
        self.line = line
        self.calls: list[str] = []    # 同模块内调用到的其它 api 符号名

    @property
    def key(self):
        return f"{rel(self.module)}::{self.name}"


def _line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def resolve_spec(spec: str, importer: str) -> str | None:
    """把 import 说明符解析成仓库内绝对路径。支持 '@/'(vite alias→src) 与相对路径。"""
    if spec.startswith("@/"):
        base = FRONTEND_SRC
        tail = spec[2:]
    elif spec.startswith("."):
        base = os.path.dirname(importer)
        tail = spec
    else:
        return None                      # 裸包名（vue/axios/element-plus…）不追
    p = os.path.normpath(os.path.join(base, tail)).replace("\\", "/")
    for cand in (p, p + ".js", p + ".vue", p + ".ts",
                 os.path.join(p, "index.js"), os.path.join(p, "index.vue")):
        if os.path.isfile(cand):
            return apath(cand)           # 与索引键同形态（正斜杠绝对路径）
    return None


class FrontendIndex:
    def __init__(self):
        self.symbols: dict[str, ApiSymbol] = {}        # "api.js::name" → symbol
        self.exports: dict[str, set[str]] = defaultdict(set)   # api 文件 → 导出符号名
        self.re_exports: dict[str, dict[str, str]] = {}  # api/index.js → 别名 → 目标模块
        # 符号 → 非 api 层调用方（入口）
        self.consumers: dict[str, set[str]] = defaultdict(set)
        # 直接用 http 打后端的非 api 层文件：url → {文件}
        self.direct_calls: dict[str, set[str]] = defaultdict(set)
        # 符号 → 引用它的 api 层文件（用于闭包上卷）
        self.api_layer_refs: dict[str, set[str]] = defaultdict(set)
        self.component_refs: dict[str, set[str]] = defaultdict(set)  # 组件 → 引用方
        self.file_imports: dict[str, set[str]] = defaultdict(set)
        self._store: dict[str, str] = {}             # 绝对路径 → 相对路径（缓存）

    # ── api 层：导出符号 → http 端点 ──
    def scan_api_layer(self) -> None:
        api_files = [os.path.join(dp, f)
                     for dp, _, fs in os.walk(API_DIR) for f in fs
                     if f.endswith((".js", ".ts"))]
        for f in api_files:
            self._scan_api_file(f)

    def _scan_api_file(self, path: str) -> None:
        path = apath(path)                  # 键统一正斜杠，否则与 resolve_spec 查不到
        text = read(path)
        exported: set[str] = set()

        # export * as X from './y'   （api/index.js 的命名空间再导出）
        for m in EXPORT_AS.finditer(text):
            alias, spec = m.group(1), m.group(2)
            target = resolve_spec(spec, path)
            self.re_exports[path] = self.re_exports.get(path, {})
            self.re_exports[path][alias] = target or spec
            exported.add(alias)

        # export function / export const  → 抓函数体里的 http 调用
        for m in EXPORT_FN.finditer(text):
            exported.add(m.group(1))
        for m in EXPORT_CONST.finditer(text):
            exported.add(m.group(1))

        for name in exported:
            if name in self.re_exports.get(path, {}):
                continue                     # 命名空间别名，单独处理
            sym = self._extract_symbol(path, text, name)
            if sym:
                self.symbols[sym.key] = sym
                self.exports[path].add(name)
            else:
                self.exports[path].add(name)  # 无 http 调用的纯逻辑导出

        # export { a, b } from './y'  → 转发
        for m in EXPORT_FROM.finditer(text):
            target = resolve_spec(m.group(1), path)
            if not target:
                continue
            for nm in self.exports.get(target, set()):
                self.exports[path].add(nm)
        for m in EXPORT_LIST.finditer(text):
            for part in m.group(1).split(","):
                nm = part.split(" as ")[-1].strip()
                if nm:
                    self.exports[path].add(nm)

    def _extract_symbol(self, path: str, text: str, name: str) -> ApiSymbol | None:
        """定位 `name` 的定义，取其（近似）函数体，找 http 调用与内部符号调用。"""
        patterns = [
            re.compile(rf"^\s*(?:export\s+)?(?:async\s+)?function\s+{re.escape(name)}\s*\(", re.M),
            re.compile(rf"^\s*(?:export\s+)?const\s+{re.escape(name)}\s*=\s*(?:async\s*)?\(", re.M),
            re.compile(rf"^\s*(?:export\s+)?const\s+{re.escape(name)}\s*=\s*(?:async\s+)?\w+\s*=>", re.M),
        ]
        start = None
        for pat in patterns:
            m = pat.search(text)
            if m:
                start = m.start()
                break
        if start is None:
            return None
        op = text.find("(", start)
        if op < 0:
            return None
        close = match_paren(text, op)
        if close < 0:
            return None
        line = _line_of(text, start)

        # ⚠️ 关键：close 是**参数列表**的右括号，不是函数体。
        # 函数体要从 close 之后找 `{` 再配平；箭头函数单表达式体则取到语句末。
        body = None
        brace = text.find("{", close)
        if brace != -1:
            end = match_brace(text, brace)
            if end > 0:
                cand_body = text[brace:end + 1]
                # 排除「参数默认值里的对象」：体太短且不含 http 调用时不算
                if HTTP_CALL.search(cand_body) or FETCH_CALL.search(cand_body):
                    body = cand_body
        if body is None:
            stop = len(text)
            for sep in ("\n\n", ";"):
                i = text.find(sep, close)
                if i != -1:
                    stop = min(stop, i)
            body = text[close:min(stop, close + 4000)]

        best = None
        for m in HTTP_CALL.finditer(body):
            best = ApiSymbol(path, name, m.group(1).upper(), m.group("path"), line)
            break
        if best is None:
            for m in FETCH_CALL.finditer(body):
                best = ApiSymbol(path, name, "GET", m.group("path"), line)
                break

        sym = best or ApiSymbol(path, name, None, None, line)
        # 同模块内调用到的其它导出符号（建立 api 层内部依赖）
        for other in self.exports.get(path, set()):
            if other == name:
                continue
            if re.search(rf"\b{re.escape(other)}\s*\(", body):
                sym.calls.append(other)
        return sym

    # ── 全前端：import 解析 → 调用方索引 ──
    def scan_consumers(self) -> None:
        for f in iter_source_files(FRONTEND_SRC):
            self._scan_consumer(f)

    def _scan_consumer(self, path: str) -> None:
        path = apath(path)                  # 键统一正斜杠，与 exports/api_layer_refs 对齐
        text = read(path)
        rpath = self._store.setdefault(path, rel(path))
        is_api_layer = apath(path).startswith(apath(API_DIR) + "/")
        specs: list[str] = []
        for m in IMPORT_STMT.finditer(text):
            specs.append(m.group("spec"))
        for m in IMPORT_DYNAMIC.finditer(text):
            specs.append(m.group(1))
        for m in BARE_IMPORT.finditer(text):
            specs.append(m.group(1))

        for spec in specs:
            target = resolve_spec(spec, path)
            if not target:
                continue
            rtarget = self._store.setdefault(target, rel(target))
            self.file_imports[rpath].add(rtarget)
            if target.endswith(SOURCE_EXT) and not target.startswith(apath(API_DIR) + "/"):
                self.component_refs[rtarget].add(rpath)
            if not is_api_layer:
                # 命名空间别名：import { aiToolsApi } from '@/api'
                for mod, alias_map in self.re_exports.items():
                    if rtarget == rel(mod):
                        for alias, tgt in alias_map.items():
                            if re.search(rf"\b{re.escape(alias)}\s*\.", text):
                                for nm in self.exports.get(tgt, set()):
                                    self.consumers[f"{rel(tgt)}::{nm}"].add(rpath)
                # 具名导入：import { batchValidate } from '@/api/aiTools'
                for stmt in IMPORT_STMT.finditer(text):
                    if resolve_spec(stmt.group("spec"), path) != target:
                        continue
                    clause = stmt.group("clause")
                    ns = re.search(r"\*\s+as\s+(\w+)", clause)
                    if ns:
                        for nm in self.exports.get(target, set()):
                            if re.search(rf"\b{re.escape(ns.group(1))}\s*\.\s*{re.escape(nm)}\b", text):
                                self.consumers[f"{rtarget}::{nm}"].add(rpath)
                        continue
                    brace = re.search(r"\{([^}]*)\}", clause)
                    if not brace:
                        continue
                    for part in brace.group(1).split(","):
                        nm = part.split(" as ")[0].strip()
                        if not nm:
                            continue
                        if not re.search(rf"\b{re.escape(nm)}\b", text):
                            continue
                        self.consumers[f"{rtarget}::{nm}"].add(rpath)

        if not is_api_layer:
            for m in HTTP_CALL.finditer(text):
                self.direct_calls[full_url(m.group("path"))].add(rpath)
            for m in FETCH_CALL.finditer(text):
                self.direct_calls[full_url(m.group("path"))].add(rpath)

    # ── api 层内部引用（闭包上卷用） ──
    def scan_api_layer_refs(self) -> None:
        for f in iter_source_files(API_DIR):
            f = apath(f)
            text = read(f)
            rf_ = self._store.setdefault(f, rel(f))
            for stmt in IMPORT_STMT.finditer(text):
                target = resolve_spec(stmt.group("spec"), f)
                if not target:
                    continue
                rt = self._store.setdefault(target, rel(target))
                clause = stmt.group("clause")
                brace = re.search(r"\{([^}]*)\}", clause)
                names = []
                if brace:
                    names = [p.split(" as ")[0].strip() for p in brace.group(1).split(",")]
                elif re.search(r"\*\s+as\s+(\w+)", clause):
                    names = ["*"]
                for nm in names:
                    if nm == "*":
                        for real in self.exports.get(target, set()):
                            self.api_layer_refs[f"{rt}::{real}"].add(rf_)
                    elif nm:
                        self.api_layer_refs[f"{rt}::{nm}"].add(rf_)

    # ── 上卷：把 api 层内部调用折叠成「入口调用方」 ──
    def entry_consumers(self, sym_key: str) -> set[str]:
        """符号的真实入口调用方（递归穿透 api 层 re-export / 内部调用）。

        ⚠️ 键类型必须全程一致。本索引里有两套键，混用会让分支静默失效：
          · self.exports   以**绝对路径**为键（scan_api_layer 走 os.walk(API_DIR)）
          · file_imports /
            api_layer_refs 的值 / consumers 的文件部分 以**相对路径**为键
        因此查 self.exports 时必须把 ref_file 还原成绝对路径；
        用相对路径去查只会恒得空集，让「api 层内部调用」这条上卷路径形同虚设。
        """
        seen: set[str] = set()
        frontier = {sym_key}
        api_prefix = rel(API_DIR) + "/"          # 相对形态的 api 层前缀
        while frontier:
            nxt: set[str] = set()
            for k in frontier:
                for c in self.consumers.get(k, ()):
                    if c not in seen:
                        seen.add(c)
                for ref_file in self.api_layer_refs.get(k, ()):
                    # ref_file 是**相对**路径；exports 的键是绝对路径 → 需还原。
                    # ⚠️ 必须走 apath()：os.path.join 在 Windows 上拼出反斜杠，
                    # 与 exports 的正斜杠键对不上，会让整个上卷分支恒空。
                    abs_ref = apath(os.path.join(REPO, ref_file))
                    for sym2 in self.exports.get(abs_ref, set()):
                        k2 = f"{ref_file}::{sym2}"
                        if k2 not in seen:
                            nxt.add(k2)
                    # api 层文件被非 api 层直接 import 整个命名空间的情形。
                    # ⚠️ 排除条件必须用**相对**前缀比较：other 是相对路径，
                    # 拿绝对 API_DIR 去 startswith 恒为 False，会把 api 层文件
                    # 误当成入口调用方（方向是漏拦：让本该 BLOCK 的被放过）。
                    for other, imports in self.file_imports.items():
                        if ref_file in imports and not other.startswith(api_prefix):
                            if other not in seen:
                                seen.add(other)
            frontier = nxt - seen
        return seen


# ══════════════════════════════════════════════════════════════════════
# 3. 后端存活「写入字段」（serializer 声明的可写关联字段）
# ══════════════════════════════════════════════════════════════════════
FIELD_DECL = re.compile(
    r"^\s*(?P<name>\w+_ids?)\s*=\s*serializers\.\w+", re.M)
READONLY = re.compile(r"read_only_fields\s*=\s*\[([^\]]*)\]", re.S)


def load_writable_fields() -> dict[str, dict]:
    """提取 serializer 里显式声明的可写关联字段（L2 字段级判定的地基）。"""
    fields: dict[str, dict] = {}
    root = os.path.join(BACKEND, "apps")
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for fn in fns:
            if not fn.endswith("serializers.py"):
                continue
            p = os.path.join(dp, fn)
            text = read(p)
            ro_blob = "\n".join(READONLY.findall(text))
            for m in FIELD_DECL.finditer(text):
                name = m.group("name")
                if re.search(rf"\b{re.escape(name)}\b", ro_blob):
                    continue
                line = _line_of(text, m.start())
                fields.setdefault(name, {
                    "name": name, "source": p, "line": line,
                    "snippet": text[m.start():text.find("\n", m.start())].strip()[:160],
                })
    return fields


# ── 字段「写入方」检测（启发式，规则编号会在报告里标注） ──
def field_writers(field: str, text: str) -> list[tuple[str, str]]:
    """判断 text 里哪些位置把 `field` **写入**了提交载荷。

    区分读/写是关键：现役页面完全可能
        const d = await getProduct(id); console.log(d.research_goal_ids)   ← 读
    却从不
        payload.research_goal_ids = ids                                  ← 写
    只做子串匹配会把「读」误判成「有入口」，从而漏报。

    规则：
      H1  `<容器>.<field> =`                容器名在 WRITE_CONTAINERS 白名单
      H2  `payload = { ... <field>: ... }`  对象字面量内的 key（花括号配平）
      H3  http.<verb>(...) 或 导入的 api 函数调用实参内的 `<field>:` key
    """
    hits: list[tuple[str, str]] = []
    seen = set()

    # H1
    for c in WRITE_CONTAINERS:
        for m in re.finditer(rf"\b{re.escape(c)}\s*\.\s*{re.escape(field)}\s*=(?!=)", text):
            key = ("H1", _line_of(text, m.start()))
            if key not in seen:
                seen.add(key)
                hits.append(key)

    # H2：payload = { ... }
    for m in re.finditer(r"\b\w+\s*=\s*\{", text):
        op = text.find("{", m.start())
        end = match_brace(text, op)
        if end < 0:
            continue
        block = text[op:end]
        for fm in re.finditer(rf"(?<![\w.$]){re.escape(field)}\s*:", block):
            key = ("H2", _line_of(text, op + fm.start()))
            if key not in seen:
                seen.add(key)
                hits.append(key)

    # H3：函数调用实参里的 key
    for m in re.finditer(r"\b(?:http|axios|api|client)\s*\.\s*(?:get|post|put|patch|delete)\s*\(", text):
        op = text.find("(", m.start())
        end = match_paren(text, op)
        if end < 0:
            continue
        block = text[op:end]
        for fm in re.finditer(rf"(?<![\w.$]){re.escape(field)}\s*:", block):
            key = ("H3", _line_of(text, op + fm.start()))
            if key not in seen:
                seen.add(key)
                hits.append(key)

    return hits


# ══════════════════════════════════════════════════════════════════════
# 4. 闸门主体
# ══════════════════════════════════════════════════════════════════════
VERDICT_BLOCK = "BLOCK"
VERDICT_OK = "OK"
VERDICT_WARN = "WARN"


class Finding:
    def __init__(self, level, verdict, title, evidence, detail, hint=""):
        self.level = level          # L1 端点级 / L2 字段级 / L3 结构级
        self.verdict = verdict
        self.title = title
        self.evidence = evidence    # 证据等级 E1/E2/E3
        self.detail = detail
        self.hint = hint

    def to_dict(self):
        return {"level": self.level, "verdict": self.verdict, "title": self.title,
                "evidence": self.evidence, "detail": self.detail, "hint": self.hint}


def _sym_use_re(name: str) -> re.Pattern:
    r"""匹配「导出符号 name 被真实使用」，且不被更长标识符的尾部骗到。

    两种真实调用形态都必须认：
      · 裸调用     getSdsList(id)
      · 命名空间   documentsApi.getSdsList(id)

    ⚠️ 这里的负向前瞻只放行 [\w$]（标识符字符）作前缀，**故意放行 '.'**：
      · 放行 '.'  → `documentsApi.getSdsList(` 能命中（限定名访问）。
      · 挡住 [\w$] → `fooBar(` 不会被 `bar` 命中（防子串误匹配）。
    所以「防子串」靠的是 \w 而不是 '.'；把 '.' 也挡掉（原先的 [\w.$]）
    正是 P0 的第二重根因 —— 它把限定名访问一并挡了。
    注：尾部 [\.(] 要求符号被当作调用/属性用，纯提及（注释、字符串里
    出现单词）不算。放行 '.' 只会带来「误认成调用」的偏保守方向，
    对删除闸门而言是安全侧（多拦而非漏放）。
    """
    return re.compile(rf"(?<![\w$]){re.escape(name)}\s*[\.(]")


class Gate:
    def __init__(self, backend: BackendIndex, frontend: FrontendIndex):
        self.be = backend
        self.fe = frontend
        self.fields = load_writable_fields()

    # ── 待删文件使用的 api 符号 ──
    def symbols_used_by(self, text: str) -> set[str]:
        """一个文件用到了哪些 api 层导出符号。

        不依赖 importer 真实存在（事后审计时文件已删），
        所以按「导出符号名 + 实际调用」宽松匹配。
        """
        used = set()
        exported_by_name: dict[str, set[str]] = defaultdict(set)
        for key in self.fe.symbols:
            mod, name = key.split("::")
            exported_by_name[name].add(mod)
        for name in exported_by_name:
            if _sym_use_re(name).search(text):
                used.add(name)
        # 命名空间别名：aiToolsApi.batchValidate(...)
        for mod, alias_map in self.fe.re_exports.items():
            for alias, tgt in alias_map.items():
                if re.search(rf"\b{re.escape(alias)}\s*\.", text):
                    for nm in self.fe.exports.get(tgt, set()):
                        if re.search(rf"\b{re.escape(alias)}\s*\.\s*{re.escape(nm)}\b", text):
                            used.add(nm)
        return used

    # ── 主检查 ──
    def _direct_callers_by_endpoint(self) -> dict[str, set]:
        """把「非 api 层直接 http/fetch 调用」按**后端端点**聚合。

        direct_calls 的 key 是前端写的 URL 字面量（尾斜杠、`${}` 模板串都可能与
        后端注册形式不同），所以必须经 be.match() 归一后再挂到 ep.path 上。
        ⚠️ 必须逐 verb 尝试：be.match 会做动词匹配，而像 generate-seo 这种
        只注册了 POST 的 @action，用固定 GET 去解析会解析失败。
        """
        out: dict[str, set] = defaultdict(set)
        for url, files in self.fe.direct_calls.items():
            for verb in HTTP_VERBS:
                m = self.be.match(verb.upper(), url)
                if m is not None:
                    out[m.path] |= files
                    break
        return out

    def check(self, targets: list[dict]) -> dict:
        """targets: [{'path': relpath, 'text': content}]（text 可来自 git）"""
        findings: list[Finding] = []
        target_paths = {t["path"] for t in targets}

        # 逐文件分析（不合并 blob —— 合并会让行号失真，指向别的文件）
        used_syms: set[str] = set()
        for t in targets:
            used_syms |= self.symbols_used_by(t["text"])

        # ── L1 端点级：唯一入口 ──
        # 按「(method, path)」聚合；同一端点被多个符号打到时合并，
        # 不能用 path 当 key 直接覆盖（否则后写入的符号会顶掉真正的调用方）。
        #
        # ⚠️ 「其他调用方」必须把**非 api 层的直接 http/fetch 调用**算进去，
        # 且要按端点解析、不能按字符串精确查表：
        #   · 前端常写 `/products/${id}/generate-seo/`（带尾斜杠），
        #     而 @action 注册出的是 `/products/{id}/generate-seo`（无尾斜杠）
        #     —— 精确查表必然落空，把「还有直接调用方」误判成「唯一入口」；
        #   · build_map 早就用 be.match() 做了这个解析，这里若不同步，
        #     同一份事实会在 --map 与 --check 里得出相反结论。
        # 实测该 bug 会把 ProductEditPage.vue:423 的 generate-seo 直接调用
        # 漏掉，进而对 seo.js 误报 WARN。
        direct_by_ep = self._direct_callers_by_endpoint()

        seen_ep: dict[tuple, dict] = {}
        for name in sorted(used_syms):
            keys = [k for k in self.fe.symbols if k.endswith("::" + name)]
            for key in keys:
                sym = self.fe.symbols[key]
                if not sym.http or not sym.path:
                    continue
                url = full_url(sym.path)
                ep = self.be.match(sym.http, url)
                if ep is None:
                    continue                      # 该 URL 已不在后端 ⇒ 真死代码
                others = (self.fe.entry_consumers(key) |
                          direct_by_ep.get(ep.path, set())) - target_paths
                if others:
                    continue
                has_test, test_why = self.be.has_test(ep.path)
                if has_test:
                    ev = "E1"
                else:
                    ev = "E3"
                verdict = VERDICT_BLOCK if has_test else VERDICT_WARN
                k2 = (ep.method if ep.method != "ANY" else sym.http, ep.path)
                info = seen_ep.setdefault(k2, {
                    "url": ep.path, "method": k2[0], "view": ep.view,
                    "backend": f"{rel(ep.source)}:{ep.line}", "syms": [],
                    "evidence": ev, "test": test_why, "verdict": verdict,
                })
                if key not in info["syms"]:
                    info["syms"].append(key)
                if has_test and info["evidence"] != "E1":
                    info["evidence"] = "E1"
                    info["verdict"] = VERDICT_BLOCK

        for _k, info in sorted(seen_ep.items(), key=lambda kv: kv[1]["url"]):
            findings.append(Finding(
                "L1", info["verdict"],
                f"端点失去唯一前端入口：{info['method']} {info['url']}",
                info["evidence"],
                f"后端 {info['view']} 仍注册于 {info['backend']}"
                + (f"；{info['test']}" if info["test"] else "；未找到测试覆盖")
                + f"；前端唯一调用方 = 待删文件（经 {'、'.join(info['syms'])}）",
                "恢复该入口，或先补上替代 UI 并证明能力等价（逐项举证，不接受打包结论）"))

        # ── L2 字段级：serializer 存活字段失去唯一写入方 ──
        for fname, finfo in sorted(self.fields.items()):
            in_target: list[str] = []
            for t in targets:
                for rule, line in field_writers(fname, t["text"]):
                    in_target.append(f"{t['path']}:{line}({rule})")
            if not in_target:
                continue
            others: dict[str, list] = defaultdict(list)
            for f in iter_source_files(FRONTEND_SRC):
                r = rel(f)
                if r in target_paths:
                    continue
                for rule, line in field_writers(fname, read(f)):
                    others[r].append(f"{line}({rule})")
            if others:
                continue
            # 后端是否真的还在消费这个字段（级联解析等）
            cascade = self._backend_consumes(fname)
            verdict = VERDICT_BLOCK if cascade else VERDICT_WARN
            findings.append(Finding(
                "L2", verdict,
                f"写入字段失去唯一前端入口：{fname}",
                "E1" if cascade else "E3",
                f"后端 {rel(finfo['source'])}:{finfo['line']} 仍声明该字段"
                + ("，且 create/update 仍在级联消费它" if cascade else "")
                + f"；待删文件写入于 {', '.join(in_target)}"
                + "；其余前端文件只读取、从不提交该字段",
                "取出数据 ≠ 提供能力。要么恢复写入 UI，要么明确记录该能力已废弃"))

        # ── L3 结构级：删除后新暴露的孤儿组件 ──
        # ⚠️ file_imports 的 key 是**仓库相对路径**（_scan_consumer 里
        # `rpath = self._store.setdefault(path, rel(path))`），
        # 而 targets 里存的是 `t["abs"]` 绝对路径 —— 两者永不相等，
        # L3 会**整层静默失效**（既不报错也不产出任何 finding）。
        # 这里必须用 t["path"]。已实测：AdminOrdersPage.vue
        # 按 abs 查得 0 条、按 rel 查得 3 条。
        for t in targets:
            for imported in self.fe.file_imports.get(t["path"], set()):
                if rel(imported) in target_paths:
                    continue
                refs = self.fe.component_refs.get(imported, set()) - target_paths
                if not refs and rel(imported) not in target_paths:
                    findings.append(Finding(
                        "L3", VERDICT_WARN,
                        f"删除后产生零引用文件：{rel(imported)}",
                        "E3",
                        f"仅被 {rel(t['path'])} 引用",
                        "确认它确实无入口；否则说明入口早已断裂，属另一个待修问题"))

        blocked = [f for f in findings if f.verdict == VERDICT_BLOCK]
        return {
            "verdict": VERDICT_BLOCK if blocked else VERDICT_OK,
            "targets": sorted(target_paths),
            "findings": [f.to_dict() for f in findings],
            "block_count": len(blocked),
            "warn_count": len(findings) - len(blocked),
        }

    def _backend_consumes(self, field: str) -> bool:
        """字段是否在后端逻辑里真的被读（级联解析 / _sync_* 等），而不只是声明。"""
        root = os.path.join(BACKEND, "apps")
        pat = re.compile(rf"\b{re.escape(field)}\b")
        for dp, dn, fns in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for fn in fns:
                if not fn.endswith(".py") or fn == "serializers.py":
                    if not (fn.endswith("serializers.py") and "commerce" in dp):
                        continue
                p = os.path.join(dp, fn)
                text = read(p)
                for m in pat.finditer(text):
                    line_start = text.rfind("\n", 0, m.start()) + 1
                    line = text[line_start:text.find("\n", m.start())]
                    # 排除纯声明行与 docstring
                    if re.match(rf"\s*#", line) or field + " = serializers." in line:
                        continue
                    if line.strip().startswith(('"""', "'''")):
                        continue
                    return True
        return False


# ══════════════════════════════════════════════════════════════════════
# 5. 映射表
# ══════════════════════════════════════════════════════════════════════
def build_map(be: BackendIndex, fe: FrontendIndex, verbose: bool = False) -> dict:
    """后端存活端点 → 前端调用方。零调用方 = 潜在孤儿能力。

    按 **URL 路径聚合**（不按 method）：DRF router 的
    GET/POST /x/ + GET/PUT/PATCH/DELETE /x/{id}/ 若按 method 展开，
    一条能力会被算成 6 条，「端点总数」与「孤儿数」双双虚高。
    """
    # 先算「每个 URL 被哪些 api 符号 / 直接调用打到」
    url_callers: dict[str, set[str]] = defaultdict(set)
    url_via: dict[str, set[str]] = defaultdict(set)
    url_methods: dict[str, set[str]] = defaultdict(set)

    for key, sym in fe.symbols.items():
        if not sym.http or not sym.path:
            continue
        m = be.match(sym.http, sym.path)
        if not m:
            continue
        url_methods[m.path].add(sym.http)
        cons = fe.entry_consumers(key)
        if cons:
            url_callers[m.path] |= cons
            url_via[m.path].add(key)

    # 直接 http/fetch 调用：同样必须逐 verb 尝试。
    # 固定 be.match("GET", url) 会漏掉只注册了 POST/PATCH 的端点
    # （实测 /products/{X}/generate-seo 就是 POST-only，会被整条丢掉），
    # 导致 --map 把它误列为「零前端入口」，与 --check 的结论互相矛盾。
    for url, files in fe.direct_calls.items():
        m = None
        for verb in HTTP_VERBS:
            m = be.match(verb.upper(), url)
            if m:
                url_methods[m.path].add(verb.upper())
                break
        if not m:
            continue
        url_callers[m.path] |= files
        url_via[m.path].add("直接 http/fetch 调用")

    rows = []
    seen_paths = set()
    for ep in be.routes():                      # 保持后端声明顺序
        if ep.path in seen_paths:
            continue
        seen_paths.add(ep.path)
        declared = [e for e in be.endpoints if e.path == ep.path]
        methods = sorted({e.method for e in declared} - {"ANY"}) or ["ANY"]
        callers = sorted(url_callers.get(ep.path, set()))
        has_test, why = be.has_test(ep.path)
        rows.append({
            "methods": methods,
            "path": ep.path,
            "view": ep.view,
            "backend": f"{rel(ep.source)}:{ep.line}",
            "kind": sorted({e.kind for e in declared}),
            "callers": callers,
            "via": sorted(url_via.get(ep.path, set())),
            "test": has_test, "test_why": why,
            "orphan": not callers,
        })
    rows.sort(key=lambda r: r["path"])
    return {"total": len(rows),
            "orphan": sum(1 for r in rows if r["orphan"]),
            "tested": sum(1 for r in rows if r["test"]),
            "rows": rows}


def print_map(m: dict, verbose: bool) -> None:
    print("=" * 100)
    print("后端存活端点 → 前端调用方 映射表（按 URL 聚合）")
    print("=" * 100)
    n_orph = m["orphan"]
    n_live = m["total"] - n_orph
    print(f"URL 总数 {m['total']}｜有测试 {m['tested']}｜"
          f"有前端入口 {n_live}｜⚠️ 零前端入口（潜在孤儿能力） {n_orph}")

    # 孤儿清单是本表的核心价值，默认全量列出；有入口的项按 verbose 决定详略
    print("\n" + "#" * 100)
    print(f"# 第一部分：⚠️ 零前端入口的后端存活能力（{n_orph} 条）")
    print("#   ⇒ 这些能力后端健在，但没有任何前端入口。要么补 UI，要么显式记录废弃。")
    print("#" * 100)
    orph_rows = [r for r in m["rows"] if r["orphan"]]
    orph_rows.sort(key=lambda r: (not r["test"], r["path"]))
    for r in orph_rows:
        tst = "有测试" if r["test"] else "无测试"
        print(f"  ⚠️  {','.join(r['methods']):<22} {r['path']}")
        print(f"        后端 {r['view']} @ {r['backend']}  ({'/'.join(r['kind'])}, {tst})")

    print("\n" + "#" * 100)
    print(f"# 第二部分：有前端入口的能力（{n_live} 条）")
    print("#" * 100)
    for r in m["rows"]:
        if r["orphan"]:
            continue
        tst = "T" if r["test"] else "-"
        print(f"[{tst}] {','.join(r['methods']):<22} {r['path']}"
              f"  ← {len(r['callers'])} 入口")
        if verbose:
            for c in r["callers"]:
                print(f"        · {c}")
            if r["via"]:
                print(f"        经由: {', '.join(r['via'])}")
    if not verbose:
        print("  （--verbose 展开每个入口文件与经由符号）")


# ══════════════════════════════════════════════════════════════════════
# 6. CLI
# ══════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="删除前「能力入口丢失」闸门",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--map", action="store_true", help="输出端点→调用方映射表")
    ap.add_argument("--verify-map", action="store_true",
                    help="校验已提交的映射表是否与当前代码一致（漂移检测）；不一致退出 1")
    ap.add_argument("--verbose", action="store_true", help="映射表输出全部明细")
    ap.add_argument("--check", nargs="*", metavar="FILE",
                    help="删除前预演：这些文件若被删会怎样")
    ap.add_argument("--audit", action="store_true",
                    help="事后审计：文件已从磁盘消失，用 --git-rev 取回内容")
    ap.add_argument("--git-rev", default="HEAD",
                    help="配合 --audit：从该 rev 取回文件内容")
    ap.add_argument("--paths", nargs="*", default=[],
                    help="配合 --audit：已删文件的仓库相对路径")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--out", metavar="FILE",
                    help="把输出写入文件；--map 时默认 deliverables/capability_map.txt")
    ap.add_argument("--force", action="store_true", help="即使 BLOCK 也退出 0")
    args = ap.parse_args(argv)

    t0 = time.time()
    if not os.path.isdir(BACKEND) or not os.path.isdir(FRONTEND_SRC):
        print(f"[错误] 仓库结构不符：{REPO}", file=sys.stderr)
        return 2

    be = BackendIndex().build()
    fe = FrontendIndex()
    fe.scan_api_layer()
    fe.scan_api_layer_refs()
    fe.scan_consumers()
    gate = Gate(be, fe)
    t_index = time.time() - t0

    # ── 映射表模式 ──
    if args.map:
        m = build_map(be, fe, args.verbose)
        if args.json:
            _emit(json.dumps(m, ensure_ascii=False, indent=2), args.out)
        else:
            text = render_map_text(m, be, fe, args.verbose, t_index, time.time() - t0)
            _emit(text, args.out or os.path.join(REPO, "deliverables", "capability_map.txt"))
        return 0

    # ── 漂移检测：已提交的映射表是否还跟得上代码 ──
    if args.verify_map:
        if args.json:
            print("[错误] --verify-map 不能与 --json 同用（json 产物格式不同）", file=sys.stderr)
            return 2
        target = args.out or os.path.join(REPO, "deliverables", "capability_map.txt")
        if not os.path.isfile(target):
            print(f"[缺失] 找不到 {rel(target)}；请先跑："
                  f"python scripts/capability_guard.py --map", file=sys.stderr)
            return 1
        m = build_map(be, fe, args.verbose)
        fresh = render_map_text(m, be, fe, args.verbose, t_index, time.time() - t0)
        diff = diff_map_text(read(target), fresh)
        if not diff:
            print(f"[OK] {rel(target)} 与当前代码一致")
            return 0
        print(f"[漂移] {rel(target)} 已过时 —— 生成物与当前代码不一致", file=sys.stderr)
        for line in diff[:40]:
            print(line, file=sys.stderr)
        if len(diff) > 40:
            print(f"...（共 {len(diff)} 行差异，已截断）", file=sys.stderr)
        print("\n修复：python scripts/capability_guard.py --map && "
              "git add deliverables/capability_map.txt", file=sys.stderr)
        return 1

    # ── 检查模式 ──
    targets: list[dict] = []
    if args.check:
        for p in args.check:
            ap_ = p if os.path.isabs(p) else os.path.join(REPO, p)
            if not os.path.isfile(ap_):
                print(f"[错误] 文件不存在：{p}", file=sys.stderr)
                return 2
            targets.append({"path": rel(ap_), "abs": ap_, "text": read(ap_)})
    if args.audit:
        if not args.paths:
            print("[错误] --audit 需要 --paths 指定已删文件路径", file=sys.stderr)
            return 2
        for p in args.paths:
            content = git_show(args.git_rev, p)
            if content is None:
                print(f"[错误] git 取不回内容：{args.git_rev}:{p}", file=sys.stderr)
                return 2
            targets.append({"path": p,
                            "abs": os.path.join(REPO, p), "text": content})
    if not targets:
        ap.print_help()
        return 2

    result = gate.check(targets)
    result["timing_sec"] = round(time.time() - t0, 3)
    result["index_sec"] = round(t_index, 3)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 100)
        print(f"删除前闸门｜目标 {len(targets)} 个文件｜索引 {t_index:.2f}s")
        print("=" * 100)
        for p in sorted(t["path"] for t in targets):
            print(f"  · {p}")
        print()
        if not result["findings"]:
            print("未发现能力入口丢失风险。")
            print("  ⚠️ 这不等于「可以安全删」：本闸门只覆盖"
                  "「后端存活端点 / 存活写入字段」这一类风险，"
                  "纯前端内部逻辑（组件状态、交互、样式）不在覆盖范围。")
        for f in result["findings"]:
            icon = {"BLOCK": "🛑", "WARN": "⚠️ ", "OK": "  "}[f["verdict"]]
            print(f"{icon} [{f['verdict']:<5}] [{f['level']}] {f['title']}")
            print(f"        证据等级: {f['evidence']}")
            print(f"        {f['detail']}")
            if f["hint"]:
                print(f"        ⇒ {f['hint']}")
            print()
        print(f"[结论] {result['verdict']}"
              f"（BLOCK {result['block_count']} / WARN {result['warn_count']}）"
              f"｜耗时 {result['timing_sec']:.2f}s")

    if result["verdict"] == VERDICT_BLOCK and not args.force:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
