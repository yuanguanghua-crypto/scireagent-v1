"""
TDD RED: cleanup_spurious_methodprotocol 必须保护 explicit 跨方法链接（#354）。

背景：旧 cleanup 用 `link.method_id != protocol.method_id` 判定并删除「笛卡尔残留」，
但会误删研究员显式建立的合法跨方法关联。修复：仅删 explicit=False 且
method_id != protocol.method_id 的残留；explicit=True 的合法链接一律保留。

运行时应 FAIL（MethodProtocol 尚无 explicit 字段 / cleanup 未加该保护），
直至 #354 实现后转 GREEN。
"""
from django.test import TestCase
from django.core.management import call_command

from apps.bridges.models import MethodProtocol
from apps.bridges.tests.factories import MethodProtocolFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory


class CleanupProtectionTest(TestCase):
    def test_methodprotocol_has_explicit_field(self):
        """MethodProtocol 必须新增 explicit 字段（默认 False）以区分合法显式链接。"""
        mp = MethodProtocolFactory()
        self.assertFalse(mp.explicit)

    def test_spurious_cross_link_deleted(self):
        """explicit=False 且 method != protocol.method 的笛卡尔残留 → 被删。"""
        method1 = MethodFactory()
        method2 = MethodFactory()
        protocol = ProtocolFactory(method=method1)  # canonical method1
        # 笛卡尔 bug 产物：把 protocol 挂到 method2 上，且非显式
        spurious = MethodProtocol.objects.create(method=method2, protocol=protocol,
                                                 explicit=False)
        call_command('cleanup_spurious_methodprotocol', '--no-dry-run')
        self.assertFalse(
            MethodProtocol.objects.filter(id=spurious.id).exists(),
            "笛卡尔残留应被删除")

    def test_explicit_cross_link_preserved(self):
        """explicit=True 的跨方法合法链接 → 即便 method != protocol.method 也保留。"""
        method1 = MethodFactory()
        method2 = MethodFactory()
        protocol = ProtocolFactory(method=method1)
        # 研究员显式建立的跨方法关联（合法）
        explicit_link = MethodProtocol.objects.create(method=method2, protocol=protocol,
                                                      explicit=True)
        call_command('cleanup_spurious_methodprotocol', '--no-dry-run')
        self.assertTrue(
            MethodProtocol.objects.filter(id=explicit_link.id).exists(),
            "显式合法跨方法链接必须保留")

    def test_canonical_link_preserved(self):
        """method == protocol.method 的正常链接 → 无论 explicit 与否都保留。"""
        method1 = MethodFactory()
        protocol = ProtocolFactory(method=method1)
        canonical = MethodProtocol.objects.create(method=method1, protocol=protocol,
                                                  explicit=False)
        call_command('cleanup_spurious_methodprotocol', '--no-dry-run')
        self.assertTrue(
            MethodProtocol.objects.filter(id=canonical.id).exists())
