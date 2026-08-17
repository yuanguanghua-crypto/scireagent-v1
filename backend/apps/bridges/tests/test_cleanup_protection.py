"""cleanup_spurious_methodprotocol 在「收敛冗余 Protocol.method FK」后的新语义契约（#494 Chunk3）。

背景变更（架构事实，非偏好）：
    旧命令判定标准是 `link.method_id != protocol.method_id`——即拿桥上的 method 与
    协议的 canonical method（Protocol.method 单 FK）对照，不一致就视为笛卡尔残留。
    #494 删除了冗余的 Protocol.method FK 后，MethodProtocol 桥成为协议↔方法关系的
    **唯一真源**，"一个协议合法关联多个方法"正是 facet 化的预期形态，
    因此**不存在 canonical 对照物，自动判定"虚假"在架构上永久失效**。

新语义（保守化降级，符合 Knowledge Links 铁律①最大化数据/不删链）：
    1. 不传 --ids 时：命令只做诊断报告，**绝不删除任何行**（即便带 --no-dry-run）。
    2. 传 --ids 且带 --no-dry-run 时：仅删除其中 explicit=False 的行（人工收口）。
    3. explicit=True 一律保留——即使被显式点名，也视为研究者合法建立的跨方法关联（#354）。
    4. 传 --ids 但不带 --no-dry-run：dry-run，只报告不删。
"""
from django.test import TestCase
from django.core.management import call_command

from apps.bridges.models import MethodProtocol
from apps.bridges.tests.factories import MethodProtocolFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory


class CleanupProtectionTest(TestCase):
    def test_methodprotocol_has_explicit_field(self):
        """MethodProtocol 必须有 explicit 字段（默认 False）以区分合法显式链接。"""
        mp = MethodProtocolFactory()
        self.assertFalse(mp.explicit)

    def test_no_ids_deletes_nothing_even_with_no_dry_run(self):
        """不点名 id 时，即便带 --no-dry-run 也绝不删除任何行（自动判定已失效）。"""
        method1 = MethodFactory()
        method2 = MethodFactory()
        protocol = ProtocolFactory()
        # 协议同时关联两个方法：新架构下这是合法形态，不得被判为"虚假"
        link1 = MethodProtocol.objects.create(method=method1, protocol=protocol,
                                              explicit=False)
        link2 = MethodProtocol.objects.create(method=method2, protocol=protocol,
                                              explicit=False)

        call_command('cleanup_spurious_methodprotocol', '--no-dry-run')

        self.assertTrue(MethodProtocol.objects.filter(id=link1.id).exists(),
                        "未点名 id 时不得删除任何桥行")
        self.assertTrue(MethodProtocol.objects.filter(id=link2.id).exists(),
                        "多方法关联是 facet 化合法形态，不得被自动删除")

    def test_targeted_non_explicit_link_deleted(self):
        """人工点名 id 且 explicit=False → 删除（人工收口路径）。"""
        protocol = ProtocolFactory()
        target = MethodProtocol.objects.create(method=MethodFactory(),
                                               protocol=protocol, explicit=False)
        keep = MethodProtocol.objects.create(method=MethodFactory(),
                                             protocol=protocol, explicit=False)

        call_command('cleanup_spurious_methodprotocol',
                     '--ids', str(target.id), '--no-dry-run')

        self.assertFalse(MethodProtocol.objects.filter(id=target.id).exists(),
                         "被点名的非显式桥行应被删除")
        self.assertTrue(MethodProtocol.objects.filter(id=keep.id).exists(),
                        "未被点名的桥行必须保留")

    def test_explicit_link_preserved_even_when_targeted(self):
        """explicit=True 即便被显式点名也必须保留（#354 保护不可绕过）。"""
        protocol = ProtocolFactory()
        explicit_link = MethodProtocol.objects.create(
            method=MethodFactory(), protocol=protocol, explicit=True)

        call_command('cleanup_spurious_methodprotocol',
                     '--ids', str(explicit_link.id), '--no-dry-run')

        self.assertTrue(MethodProtocol.objects.filter(id=explicit_link.id).exists(),
                        "显式关联即使被点名也必须保留")

    def test_dry_run_default_deletes_nothing(self):
        """传了 ids 但未加 --no-dry-run → dry-run，不删。"""
        protocol = ProtocolFactory()
        link = MethodProtocol.objects.create(method=MethodFactory(),
                                             protocol=protocol, explicit=False)

        call_command('cleanup_spurious_methodprotocol', '--ids', str(link.id))

        self.assertTrue(MethodProtocol.objects.filter(id=link.id).exists(),
                        "默认 dry-run 不得删除")
