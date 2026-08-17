"""S2 TDD：Method → Application 重挂核心逻辑（合成数据，不依赖真实 dev 数据）。

覆盖三件事：
 1) 真实 Method 按重挂表改挂到目标 Application（FK 变更）
 2) 伪 Method 不删除，整体重挂到隔离用 catch-all Application（F3 Option A）
 3) 重挂过程中 MethodProtocol / ProductMethod 桥接行原样保留（守铁律①不删）

真实重挂表在 apps.knowledge.services.method_remap 以常量形式存在；本测试向
apply_method_remap() 注入合成配置，验证机制本身正确。真实数据收益（非零 RG
1/9→6/9）用只读探针在真实 dev DB 跑命令后复核。
"""
from django.test import TestCase
from apps.knowledge.models import Application, Method
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ResearchGoalFactory, ProtocolFactory,
)
from apps.commerce.tests.factories import ProductFactory
from apps.bridges.models import ProductMethod, MethodProtocol
from apps.knowledge.services.method_remap import (
    apply_method_remap, PSEUDO_TARGET_APPLICATION,
)


class MethodRemapTest(TestCase):

    def setUp(self):
        # 源 Application（模拟 FL）+ 目标 Application（模拟 ClickApp）
        self.fl = ApplicationFactory(name='Fluorescent Labeling')
        self.click_app = ApplicationFactory(name='ClickApp')
        # relink 目标（模拟真实 Enzymatic Labeling）
        self.enz = MethodFactory(name='Enzymatic Labeling', application=self.fl)
        # 要重挂的真实 Method（当前错挂 FL）
        self.click = MethodFactory(name='Click Chemistry', application=self.fl)
        # 伪 Method（带一个商品 + 一个协议关联，证明 Option A 保留桥接）
        self.pseudo = MethodFactory(name='AAV pseudo method', application=self.fl)
        self.prod_x = ProductFactory(name='ProdX only-via-pseudo')
        ProductMethod.objects.create(product=self.prod_x, method=self.pseudo)
        self.proto = ProtocolFactory()
        MethodProtocol.objects.create(method=self.pseudo, protocol=self.proto)
        # 一个正常真实 Method/Application，验证不被误伤
        self.rg = ResearchGoalFactory()
        self.real_app = ApplicationFactory(name='RealApp', research_goal=self.rg)
        self.real_method = MethodFactory(name='Real Method', application=self.real_app)

    def _remap(self, dry_run=False):
        return apply_method_remap(
            remap_table={'Click Chemistry': 'ClickApp'},
            pseudo_methods=['AAV pseudo method'],
            pseudo_target_app_name=PSEUDO_TARGET_APPLICATION,
            dry_run=dry_run,
        )

    def test_remaps_real_method_fk(self):
        """真实 Method 按重挂表改挂到目标 Application。"""
        self._remap()
        self.click.refresh_from_db()
        self.assertEqual(self.click.application, self.click_app)

    def test_reparents_pseudo_method_to_catchall_not_deleted(self):
        """F3 Option A：伪 Method 不删，改挂到 catch-all Application。"""
        self.assertTrue(Method.objects.filter(name='AAV pseudo method').exists())
        self._remap()
        self.assertTrue(Method.objects.filter(name='AAV pseudo method').exists())
        catchall = Application.objects.get(name=PSEUDO_TARGET_APPLICATION)
        self.pseudo.refresh_from_db()
        self.assertEqual(self.pseudo.application, catchall)

    def test_catchall_app_is_quarantined_from_rg_tree(self):
        """catch-all 的 research_goal=None，脱离任意 RG 导航树，解除对 FL 的塌缩贡献。"""
        self._remap()
        catchall = Application.objects.get(name=PSEUDO_TARGET_APPLICATION)
        self.assertIsNone(catchall.research_goal)

    def test_preserves_product_method_bridge_when_reparenting(self):
        """重挂伪 Method 后，其 ProductMethod 桥接行原样保留（不丢、不改挂）。"""
        self._remap()
        self.assertTrue(
            ProductMethod.objects.filter(product=self.prod_x, method=self.pseudo).exists()
        )

    def test_preserves_method_protocol_bridge_when_reparenting(self):
        """重挂伪 Method 后，其 MethodProtocol 桥接行原样保留（Option A 守 Path 一）。"""
        self._remap()
        self.assertTrue(
            MethodProtocol.objects.filter(method=self.pseudo, protocol=self.proto).exists()
        )

    def test_does_not_touch_real_method_or_application(self):
        """真实 Method / Application 不受重挂影响。"""
        self._remap()
        self.real_method.refresh_from_db()
        self.assertEqual(self.real_method.application, self.real_app)
        self.assertEqual(Application.objects.get(name='RealApp').research_goal, self.rg)

    def test_dry_run_has_no_side_effects(self):
        """dry-run：不写库，但报告应记录计划动作。"""
        report = self._remap(dry_run=True)
        # FK 未改
        self.click.refresh_from_db()
        self.assertEqual(self.click.application, self.fl)
        # 伪 Method 未动、catch-all 未建
        self.assertTrue(Method.objects.filter(name='AAV pseudo method').exists())
        self.assertFalse(
            Application.objects.filter(name=PSEUDO_TARGET_APPLICATION).exists()
        )
        # 报告记录计划
        self.assertIn(('Click Chemistry', 'ClickApp'), report['remapped'])
        self.assertIn(
            ('AAV pseudo method', PSEUDO_TARGET_APPLICATION),
            report['reparented_pseudo'],
        )
        self.assertTrue(report['created_catchall_app'])
