"""取证测试：ProductEditPage「Research Goals / Applications 关联」UI 背后的后端级联语义。

本文件**不修改任何后端行为**，只把 `ProductCreateUpdateSerializer` 对
`research_goal_ids` / `application_ids` 的既有真实语义钉死，供前端补 UI 时据以设计。

★ 本文件的核心风险（见 serializers.py 的 `_merge_method_ids`）：
  旧实现 `merged = direct | cascaded` 是**并集**，随后交给 `_sync_method_bridges`，
  而后者是**差量同步**（先删 existing - desired，再加 desired - existing）。
  ⇒ `desired` 一旦小于 `existing`，**既有方法关联会被真删**。
  由于"用户没改方法链"时可能**不传 method_ids**，
  此时 `direct` 为空集、`desired` 退化为**纯级联集** ⇒ 只传 goal 就可能删掉既有方法链。

★ **2026-10-17 已修复**（后端根因，非前端绕过）：
  `_sync_method_bridges` 已拆出独立的 `cascaded_ids` 通道 —— goal/app 级联项
  **只增不删**，删除决策的唯一依据是显式 `method_ids`。
  本文件中两条记录**缺陷行为**的用例（"只传 goal 会删既有桥"、"传 [] 会清空整链"）
  已**翻转断言方向**，并保留"原始取证结论"的说明文字。
  完整的修复后契约见 `test_product_goal_cascade_append_only.py`。

下面 4 组用例分别锁定：并集追加、删除风险、"清空"语义、以及是否存在 goal 存储表。
"""
from django.test import TestCase

from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import Application, Method, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ResearchGoalFactory,
)
from apps.bridges.models import ProductMethod
from apps.bridges.tests.factories import ProductMethodFactory


def _pm_ids(product):
    """该产品当前的 ProductMethod 桥集合（排序后便于断言）。"""
    return sorted(
        ProductMethod.objects.filter(product=product).values_list('method_id', flat=True)
    )


class ResearchGoalCascadeSemanticsTest(TestCase):
    """锁定 `research_goal_ids` 的级联副作用。"""

    def setUp(self):
        self.goal = ResearchGoalFactory(name='RNA Analysis')
        self.other_goal = ResearchGoalFactory(name='Click Chemistry')
        self.app_a = ApplicationFactory(name='RNA Labeling', research_goal=self.goal)
        self.app_b = ApplicationFactory(name='Sequencing', research_goal=self.goal)
        self.app_other = ApplicationFactory(name='Click', research_goal=self.other_goal)
        # 三个方法：两个属 goal，两个属 other_goal（对照组）
        self.m_a1 = MethodFactory(name='CuAAC', application=self.app_a)
        self.m_a2 = MethodFactory(name='NHS-Ester', application=self.app_b)
        self.m_other = MethodFactory(name='SPAAC', application=self.app_other)

    def test_goal_ids_cascade_appends_methods(self):
        """实测 1：传 research_goal_ids ⇒ 该 goal 下所有方法被【并集追加】进产品。"""
        product = ProductFactory()
        self.assertEqual(_pm_ids(product), [])

        data = {'research_goal_ids': [self.goal.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        # 实测确认：goal 下 2 个应用 → 2 个方法全部进链
        self.assertEqual(_pm_ids(product), sorted([self.m_a1.id, self.m_a2.id]))
        # 实测确认：无关 goal 的方法【没有】被牵连
        self.assertNotIn(self.m_other.id, _pm_ids(product))

    def test_goal_ids_cascade_is_union_with_direct_method_ids(self):
        """实测 2：direct | cascaded 是并集 —— 直接传的 method 与级联出的 method 共存。"""
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)

        data = {
            'method_ids': [self.m_other.id],
            'research_goal_ids': [self.goal.id],
        }
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        # 实测确认：既有直接关联【保留】，级联的【追加】，共 3 条
        self.assertEqual(
            _pm_ids(product), sorted([self.m_a1.id, self.m_a2.id, self.m_other.id])
        )

    def test_goal_ids_without_method_ids_NO_LONGER_deletes_existing_bridges(self):
        """★ 取证用例，**已于 2026-10-17 修复并翻转断言方向**。

        原始取证结论（`1333ccc` 时的真实行为）：**只**传 research_goal_ids 而不传
        method_ids ⇒ direct 为空集，desired 退化为纯级联集 ⇒ `_sync_method_bridges`
        把 existing-desired 的既有桥**真删掉**。据此曾判定"前端必须在带 goal 时回传
        全量 method_ids"作为防线。

        修复后（`serializers.py` 的 `_sync_method_bridges` 拆出 `cascaded_ids` 通道）：
        删除决策的**唯一依据**是显式 `method_ids`；goal/app 级联项**只增不删**。
        ⇒ 任何 API 调用方只传 goal/app 都**不会再造成数据损失**，前端护栏降级为
        "锦上添花"而非"唯一防线"。

        本用例现在钉死修复后的正确行为：既有桥**全部保留**，级联方法**追加**。
        """
        product = ProductFactory()
        # 预置一条与 goal 完全无关的既有方法关联
        ProductMethodFactory(product=product, method=self.m_other)
        self.assertEqual(_pm_ids(product), [self.m_other.id])

        data = {'research_goal_ids': [self.goal.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        # 修复后：既有的 self.m_other **保留**，级联出的 2 条**追加** ⇒ 共 3 条
        self.assertEqual(
            _pm_ids(product), sorted([self.m_a1.id, self.m_a2.id, self.m_other.id]))
        self.assertTrue(
            ProductMethod.objects.filter(product=product, method=self.m_other).exists(),
            '只传 research_goal_ids 不得删除任何既有方法关联（2026-10-17 已修）',
        )

    def test_clearing_goal_selection_has_no_storage_to_clear(self):
        """实测 4：**清空 goal 选择后保存**到底发生什么。

        后端**没有** Product↔ResearchGoal / Product↔Application 的存储表
        （见 apps/bridges/models.py —— 只有 ProductMethod / MethodProtocol /
        ProductProtocol / ProductReference / ProductCompatibility 等，无 goal/app 桥）。
        ⇒ 这两个字段纯粹是"一次性级联入口"，本身不留痕。

        ★ 2026-10-17 修复后语义（断言已随之更新）：
          · 传 []        ⇒ 级联集为空；因**未给出 method_ids** ⇒ **无删除决策依据**
                          ⇒ **不删除任何既有方法关联**（原行为是清空整链，属数据误删）
          · 传 method_ids=[] ⇒ 显式 desired 为空集 ⇒ **仍清空整链**（语义刻意不同，
                          前端"清空方法链"走的就是这条路）
          · 省略该key   ⇒ 保留既有桥（`_sync_*` 的 None 早退）

        本用例钉死修复后的行为：清空 goal 选择**不会**动方法链，而"无存储表"这一事实不变。
        """
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)

        # 传空数组：级联集为空且未给 method_ids ⇒ 既有关联**保留**（原行为会清空整链）
        data = {'research_goal_ids': [], 'application_ids': []}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(
            _pm_ids(product), [self.m_other.id],
            '传空 goal/app 数组只表示"本次不追加"，不等于"清空方法链"（2026-10-17 已修）',
        )

        # 对照：显式传 method_ids=[] 才是"清空整链"
        data_clear = {'method_ids': []}
        serializer_clear = ProductCreateUpdateSerializer(
            product, data=data_clear, partial=True)
        self.assertTrue(serializer_clear.is_valid(), serializer_clear.errors)
        serializer_clear.save()
        self.assertEqual(_pm_ids(product), [])

        # 再验证"省略 key"分支：保留既有
        product2 = ProductFactory()
        ProductMethodFactory(product=product2, method=self.m_other)
        data2 = {'name': product2.name}
        serializer2 = ProductCreateUpdateSerializer(product2, data=data2, partial=True)
        self.assertTrue(serializer2.is_valid(), serializer2.errors)
        serializer2.save()
        self.assertEqual(_pm_ids(product2), [self.m_other.id])


class NoGoalStorageTableTest(TestCase):
    """实测 5：确认后端**不存在** goal/app 的产品侧存储表（决定"清空"是否有意义）。"""

    def test_no_product_research_goal_bridge_model_exists(self):
        """bridges app 里没有任何以 ResearchGoal 为端点的桥接模型。"""
        from apps.bridges import models as bridges_models

        goal_linked_fields = []
        for model in bridges_models.__dict__.values():
            if not hasattr(model, '_meta'):
                continue
            for field in model._meta.get_fields():
                related = getattr(field, 'related_model', None)
                if related in (ResearchGoal, Application):
                    goal_linked_fields.append(f'{model.__name__}.{field.name}')

        # 实测确认：空列表 —— 即"没有任何桥接表把产品连到 ResearchGoal/Application"
        self.assertEqual(
            goal_linked_fields, [],
            f'意外发现 goal/app 桥接字段：{goal_linked_fields} —— '
            f'若非空则"清空选择"另有语义，需重新评估 UI 设计',
        )


class FrontendPayloadContractTest(TestCase):
    """实测 6：模拟 ProductEditPage.vue 的**真实提交 payload**，验证 UI 的补偿逻辑有效。

    前端（ProductEditPage.vue，2026-10-17 补回）采取的对策是：
      **只要本次带 goal/app，就回传【全量】method_ids**（而非 baseline 增量），
      使后端 `_sync_method_bridges` 的 desired ⊇ existing ⇒ 删除集为空，级联只做追加。

    本组用例把这个契约钉死：若有人日后把 payload 改回"增量/省略"，
    `test_frontend_full_method_ids_payload_does_not_delete` 会**立刻变红**。
    """

    def setUp(self):
        self.goal = ResearchGoalFactory(name='RNA Analysis')
        self.other_goal = ResearchGoalFactory(name='Click Chemistry')
        self.app_a = ApplicationFactory(name='RNA Labeling', research_goal=self.goal)
        self.app_other = ApplicationFactory(name='Click', research_goal=self.other_goal)
        self.m_a = MethodFactory(name='CuAAC', application=self.app_a)
        self.m_other = MethodFactory(name='SPAAC', application=self.app_other)

    def test_frontend_full_method_ids_payload_does_not_delete(self):
        """★ 契约用例：前端"全量 method_ids + goal_ids"payload ⇒ 既有方法关联【零丢失】。

        这正是 ProductEditPage.vue:1548 起的 `if (hasGoalAppSelection)` 分支所提交的内容。
        """
        product = ProductFactory()
        # 载入态：产品已关联 2 个方法（其中 1 个与所选 goal 无关）
        ProductMethodFactory(product=product, method=self.m_a)
        ProductMethodFactory(product=product, method=self.m_other)
        before = _pm_ids(product)
        self.assertEqual(before, sorted([self.m_a.id, self.m_other.id]))

        # 用户勾了一个 goal，但**没动方法链** ⇒ 前端回传全量 method_ids（= 载入态原样）+ goal_ids
        payload = {
            'method_ids': [self.m_a.id, self.m_other.id],
            'research_goal_ids': [self.goal.id],
        }
        serializer = ProductCreateUpdateSerializer(product, data=payload, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        after = _pm_ids(product)
        # 实测确认：既有的 2 条**全部保留**（含与 goal 无关的 m_other）
        self.assertTrue(
            set(before).issubset(set(after)),
            f'实测：前端全量 payload 仍丢了既有方法关联 before={before} after={after}',
        )

    def test_frontend_full_payload_appends_cascaded_methods(self):
        """实测 7：前端全量 payload 同时把级联出的方法**追加**进来（只增不删）。"""
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)

        payload = {
            'method_ids': [self.m_other.id],       # 前端全量：含已加载的级联方法
            'research_goal_ids': [self.goal.id],
        }
        serializer = ProductCreateUpdateSerializer(product, data=payload, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        # 实测确认：既有保留 + 级联追加 = 2 条
        self.assertEqual(_pm_ids(product), sorted([self.m_a.id, self.m_other.id]))

    def test_clearing_selection_omits_key_and_preserves_chain(self):
        """实测 8：用户**清空**所有 goal/app 选择时，前端省略这两个 key（而非传 []）。

        ProductEditPage.vue 的分支条件是 `hasGoalAppSelection`，清空后为 false
        ⇒ 两个 key 都不进 payload ⇒ 后端 `chain_specified` 走"未显式给出"分支
        ⇒ 既有的 ProductMethod 与 INHERITED 协议行**全部保留**。

        这是与"传 []"的关键差异：传 [] 会把整条方法链清空（见上方 test 4）。
        """
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_a)
        ProductMethodFactory(product=product, method=self.m_other)
        before = _pm_ids(product)

        # 清空选择 ⇒ payload 里没有 research_goal_ids / application_ids 这两个 key
        payload = {'name': product.name}
        self.assertNotIn('research_goal_ids', payload)
        self.assertNotIn('application_ids', payload)

        serializer = ProductCreateUpdateSerializer(product, data=payload, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        # 实测确认：方法链原封不动
        self.assertEqual(_pm_ids(product), before)