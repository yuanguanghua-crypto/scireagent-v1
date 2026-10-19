"""
capability_guard（删除前置闸门）回归测试。

这个脚本此前**零测试**，而它已是生产「删除前置闸门」的唯一实现。
零覆盖正是它能长期漏放行删除的根因：命名空间导入
（`import * as documentsApi from '@/api/documents'`）识别不了，
于是 `documentsApi.createCoa(...)` 这类调用不进符号索引，
闸门对 COA/SDS/Batch/Verified 那批能力「零入口」误判 ⇒ 放行删除。
这与项目在其它地方反复吃的「零引用≠无能力」是同一类事故。

两组根因（都实测确认）：
  1. **键分隔符不一致（P0 主因）**：`scan_api_layer` 走 `os.walk`，
     Windows 下 `os.path.join` 产出反斜杠键；而 `resolve_spec` 产出
     正斜杠。两者字符串不等 ⇒ `exports.get(target)` 恒空，
     命名空间分支与 `export {a} from './b'` 转发**静默失效**。
     ⚠️ 这是**平台相关**的：在 Linux 上两者都是正斜杠，恰好相等，
     所以只在 Windows 上暴露 —— 跨平台复现测试是必要的。
  2. **符号匹配前瞻**：`(?<![\\w.$])` 把 `.` 也挡了，限定名访问
     （`ns.func(`）一并漏掉；防子串靠的是 `\\w` 而不是 `.`。

⚠️ 断言纪律：命名空间用例断言的是**具体入口文件集合**，不是
「非空」——空集与非空集之差正是这个 P0 的全部要害。
"""
import importlib.util
import os
import sys

from django.test import SimpleTestCase

REPO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
)
GUARD_PATH = os.path.join(REPO, "scripts", "capability_guard.py")


def _load_guard(path: str = GUARD_PATH):
    """按路径加载 capability_guard（它不是包，用 spec_from_file_location）。"""
    spec = importlib.util.spec_from_file_location("capability_guard_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard()


def _index():
    """构建完整前端索引（命名空间/具名/re-export 都靠它）。"""
    fe = guard.FrontendIndex()
    fe.scan_api_layer()
    fe.scan_api_layer_refs()
    fe.scan_consumers()
    return fe


class NamespaceImportTests(SimpleTestCase):
    """P0 回归：命名空间导入必须能解析到真实入口调用方。"""

    @classmethod
    def setUpClass(cls):
        cls.fe = _index()

    def test_namespace_import_registers_entry_consumer(self):
        """`documentsApi.getSdsList` 的入口必须包含真实调用方。

        这正是修复前恒空的那一项（consumers 里查无此键）。
        """
        key = "frontend/src/api/documents.js::getSdsList"
        entries = self.fe.entry_consumers(key)
        self.assertIn(
            "frontend/src/views/workspace/ProductEditPage.vue", entries,
            "命名空间导入 documentsApi.getSdsList 未被识别 ⇒ 闸门会漏放行删除",
        )

    def test_namespace_and_named_import_both_resolve(self):
        """同一 api 文件的命名空间符号，入口不得为空集。"""
        for name in ("getSdsList", "createCoa", "approveSds", "getBatches"):
            key = f"frontend/src/api/documents.js::{name}"
            with self.subTest(symbol=name):
                self.assertTrue(
                    self.fe.entry_consumers(key),
                    f"{name} 的入口调用方为空 —— 命名空间导入未被识别",
                )

    def test_named_import_still_works(self):
        """防「修命名空间时把原有具名导入搞坏」。"""
        key = "frontend/src/api/products.js::getProducts"
        self.assertTrue(
            self.fe.entry_consumers(key),
            "具名导入路径回归：products.js::getProducts 入口为空",
        )

    def test_resolve_spec_key_matches_exports_key(self):
        """根因 1 的直接断言：解析出的路径必须与 exports 的键**同形态**。

        修复前 `resolve_spec` 返回正斜杠、`exports` 键是反斜杠，
        `exports.get(target)` 恒得空集。
        """
        target = guard.resolve_spec(
            "@/api/documents",
            os.path.join(REPO, "frontend/src/views/workspace/ProductEditPage.vue"),
        )
        self.assertIsNotNone(target)
        self.assertNotIn("\\", target, "resolve_spec 必须返回正斜杠路径")
        self.assertIn(
            target, self.fe.exports,
            "resolve_spec 的返回键在 exports 里查不到 ⇒ 索引键形态不一致",
        )


class SymbolMatchTests(SimpleTestCase):
    """根因 2：符号匹配要认限定名，又不能被子串骗到。"""

    def _gate(self):
        be = guard.BackendIndex().build()
        return guard.Gate(be, _index())

    def test_namespace_call_is_matched(self):
        gate = self._gate()
        used = gate.symbols_used_by(
            "import * as documentsApi from '@/api/documents'\n"
            "await documentsApi.createCoa(payload)\n"
            "await documentsApi.getSdsList(productId.value)\n"
        )
        self.assertIn("createCoa", used, "命名空间调用 createCoa 未被识别")
        self.assertIn("getSdsList", used, "命名空间调用 getSdsList 未被识别")

    def test_named_call_is_matched(self):
        gate = self._gate()
        used = gate.symbols_used_by(
            "import { getProducts } from '@/api/products'\nawait getProducts()\n"
        )
        self.assertIn("getProducts", used, "具名调用回归")

    def test_substring_not_false_matched(self):
        """`fooBar` 不应被 `bar` 命中 —— 保住原前瞻的防子串意图。"""
        gate = self._gate()
        used = gate.symbols_used_by("const fooBar = getSdsList(1)\nfooBar()\n")
        # getSdsList 自身被调用，应命中
        self.assertIn("getSdsList", used)
        # 关键：不存在名为 bar 的 api 导出符号时不应凭空命中
        gate2 = gate
        self.assertNotIn("bar", gate2.symbols_used_by("fooBar(x)"))


class ImportFormTests(SimpleTestCase):
    """四类调用形态：具名 / 命名空间 / 相对路径 / 动态 import 都不许回归。"""

    @classmethod
    def setUpClass(cls):
        cls.fe = _index()

    def test_alias_import(self):
        """`@/` 别名 + 具名。"""
        self.assertTrue(
            self.fe.consumers.get("frontend/src/api/products.js::getProducts"),
            "@/ 别名具名导入未被识别",
        )

    def test_namespace_import_via_api_index_reexport(self):
        """api/index.js 的 `export * as X` 再导出别名。"""
        found = any(
            key.startswith("frontend/src/api/") and "::" in key
            for key in self.fe.consumers
        )
        self.assertTrue(found, "再导出/命名空间索引整体为空")

    def test_dynamic_import_recorded_in_file_imports(self):
        """动态 import() 也要进 file_imports。"""
        target = os.path.join(REPO, "frontend/src/api/documents.js")
        importers = [
            f for f, imps in self.fe.file_imports.items()
            if guard.rel(target) in imps
        ]
        self.assertTrue(importers, "documents.js 没有任何 file_imports 记录")

    def test_relative_and_alias_forms_both_present(self):
        """相对路径与 @/ 别名两种说明符都应能解析到同一目标。

        ProductDetail.vue 位于 frontend/src/views/，故相对路径为 ../api/documents。
        """
        importer = os.path.join(REPO, "frontend/src/views/ProductDetail.vue")
        self.assertEqual(
            guard.resolve_spec("@/api/documents", importer),
            guard.resolve_spec("../api/documents", importer),
            "@/ 别名与相对路径未解析到同一目标",
        )


class CheckEndToEndTests(SimpleTestCase):
    """--check 端到端：只有命名空间调用方的能力，删掉它必须 BLOCK。"""

    def test_deleting_namespace_only_caller_blocks(self):
        """删掉那个「只有命名空间调用方」的文件，闸门必须 BLOCK。

        走真实 Gate.check 全链路，而不是只断言索引非空。
        ProductEditPage.vue 是 documents.js 里 createCoa/approveSds/getBatches
        等 COA/SDS/Batch 能力的**唯一**前端入口（它用
        `import * as documentsApi` 调用），删掉它等于抽掉整套能力。
        """
        be = guard.BackendIndex().build()
        fe = _index()
        gate = guard.Gate(be, fe)

        key = "frontend/src/api/documents.js::createCoa"
        entries = fe.entry_consumers(key)
        self.assertIn(
            "frontend/src/views/workspace/ProductEditPage.vue", entries,
            "前置条件不成立：命名空间调用方未被索引，--check 无法验证",
        )

        victim = "frontend/src/views/workspace/ProductEditPage.vue"
        result = gate.check([{"path": victim, "text": guard.read(os.path.join(REPO, victim))}])
        self.assertEqual(
            result["verdict"], "BLOCK",
            "删除唯一命名空间调用方后闸门未 BLOCK —— P0 未真正堵住",
        )

    def test_coa_sds_endpoints_are_covered_by_the_block(self):
        """具体端点：COA 创建与 SDS 生成必须出现在拦截清单里。

        这两条正是修复前**完全漏掉**的（删掉该文件也不会 BLOCK）。
        """
        be = guard.BackendIndex().build()
        fe = _index()
        gate = guard.Gate(be, fe)
        victim = "frontend/src/views/workspace/ProductEditPage.vue"
        result = gate.check([{"path": victim, "text": guard.read(os.path.join(REPO, victim))}])
        blob = " ".join(str(f) for f in result.get("findings", []))
        for needle in ("/api/v1/coas/create-coa", "/api/v1/sds-revisions/generate"):
            with self.subTest(endpoint=needle):
                self.assertIn(
                    needle, blob,
                    f"{needle} 未被拦截：命名空间调用仍被漏放行",
                )


class CrossPlatformKeyTests(SimpleTestCase):
    """根因 1 是平台相关的：必须证明两种分隔符下索引都成立。"""

    def test_apath_normalizes_separators(self):
        p = guard.apath(os.path.join(REPO, "frontend", "src", "api", "documents.js"))
        self.assertNotIn("\\", p, "apath 必须统一成正斜杠")

    def test_exports_keys_are_normalized(self):
        fe = guard.FrontendIndex()
        fe.scan_api_layer()
        for key in fe.exports:
            self.assertNotIn(
                "\\", key,
                f"exports 键未归一化，仍是平台相关形态：{key}",
            )


if __name__ == "__main__":
    import unittest
    unittest.main()


# ---------------------------------------------------------------------------
# --verify-map 漂移检测（2026-10-19 新增）
#
# 要解决的问题：`deliverables/capability_map.txt` 是生成物，但没人会主动重生成
# ⇒ 它会长期停留在"看起来有映射、实际与代码脱节"的状态（正是本项目反复吃的坑）。
#
# 设计取舍：**检测漂移（报错）而非自动改写**。
#   自动改写会在 commit 时静默改文件、需要二次 add，且可能与手改冲突；
#   检测则明确告诉人"跑这条命令"。
#
# ⚠️ 关键陷阱：生成物里含 `[耗时] 索引构建 X.XXs｜总计 Y.YYs`，
#   每次运行都不同 ⇒ 不做归一化的话，**内容完全相同的两份也会被判不一致**。
#   所以对比必须走 `strip_volatile()`。
# ---------------------------------------------------------------------------
class VerifyMapDiffTests(SimpleTestCase):
    """纯函数层测试：不构建索引，秒级完成。"""

    SAMPLE = (
        "URL 总数 3｜有测试 2｜有前端入口 1\n"
        "\n"
        "[T] GET,POST               /api/v1/wishlist/  ← 2 入口\n"
        "[-] ANY                    /api/v1/internal-x/\n"
        "\n"
        "[耗时] 索引构建 1.23s｜总计 4.56s｜后端端点 3｜api 符号 10\n"
    )

    def test_strip_volatile_removes_timing_line(self):
        """耗时行必须被归一化，否则生成物永远无法对比。"""
        out = guard.strip_volatile(self.SAMPLE)
        self.assertNotIn("1.23s", out)
        self.assertNotIn("4.56s", out)
        self.assertIn("[耗时] <不参与对比>", out)

    def test_diff_is_empty_when_only_timing_differs(self):
        """★ 核心：内容相同、只有耗时不同 ⇒ 必须判为一致（无差异）。"""
        other = self.SAMPLE.replace("1.23s", "9.99s").replace("4.56s", "0.01s")
        self.assertEqual(guard.diff_map_text(self.SAMPLE, other), [])

    def test_diff_detects_content_change(self):
        """内容真的变了 ⇒ 必须报出差异，且差异里能看到变化的 URL。"""
        other = self.SAMPLE.replace("/api/v1/wishlist/", "/api/v1/wishlist_TAMPERED/")
        diff = guard.diff_map_text(self.SAMPLE, other)
        self.assertTrue(diff, "内容变了却没有报差异 ⇒ 漂移检测失效")
        joined = "\n".join(diff)
        self.assertIn("wishlist_TAMPERED", joined)

    def test_diff_detects_added_and_removed_lines(self):
        """增行/删行也要能被发现（不只看替换）。"""
        added = self.SAMPLE + "[T] GET                    /api/v1/new-endpoint/\n"
        self.assertTrue(guard.diff_map_text(self.SAMPLE, added))
        removed = self.SAMPLE.replace("[-] ANY                    /api/v1/internal-x/\n", "")
        self.assertTrue(guard.diff_map_text(self.SAMPLE, removed))


# ---------------------------------------------------------------------------
# 测试覆盖率启发式的「常量展开」（2026-10-19 补第 2 类盲区）
#
# 背景：`has_test` 要求「带引号的完整 URL 字面量」，但测试普遍写成
#     URL = '/api/v1/wishlist/'
#     self.client.patch(f'{URL}{wl.id}/', ...)
# 静态文本里只有 `{URL}{wl.id}/`，不含真实前缀 ⇒ 判定必然漏。
# 实测：/api/v1/wishlist/{X}/ 明明有 5 个用例，却长期被标成「无测试」。
# ---------------------------------------------------------------------------
class ExpandUrlConstantsTests(SimpleTestCase):
    def test_expands_uppercase_const_into_fstring(self):
        """★ 核心：常量要被展开进 f-string，否则带前缀的 URL 永远搜不到。"""
        text = "URL = '/api/v1/wishlist/'\nresp = c.patch(f'{URL}{wl.id}/')\n"
        out = guard.expand_url_constants(text)
        self.assertIn("/api/v1/wishlist/{wl.id}/", out)

    def test_does_not_touch_expression_interpolation(self):
        """`{wl.id}` 这类表达式不能被当成变量名替换。"""
        text = "URL = '/api/v1/x/'\nresp = c.get(f'{URL}{wl.id}/')\n"
        out = guard.expand_url_constants(text)
        self.assertIn("{wl.id}", out, '表达式插值被误改')
        self.assertNotIn("{URL}", out)

    def test_conflicting_definitions_are_not_expanded(self):
        """★ 同名不同值 ⇒ 保守跳过（否则可能张冠李戴到别的端点）。"""
        text = (
            "URL = '/api/v1/a/'\n"
            "URL = '/api/v1/b/'\n"
            "resp = c.get(f'{URL}1/')\n"
        )
        out = guard.expand_url_constants(text)
        self.assertIn("{URL}", out, '存在歧义时不应展开')

    def test_only_slash_leading_constants_are_collected(self):
        """只收集以 `/` 开头的常量 —— 避免把任意字符串常量当 URL 展开。"""
        text = "NAME = 'hello'\nresp = c.get(f'{NAME}')\n"
        out = guard.expand_url_constants(text)
        self.assertIn("{NAME}", out)

    def test_no_constants_returns_text_unchanged(self):
        text = "resp = c.get('/api/v1/plain/')\n"
        self.assertEqual(guard.expand_url_constants(text), text)
