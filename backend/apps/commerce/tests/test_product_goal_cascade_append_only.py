"""★ 契约测试：goal/app 级联是**纯追加**语义，**绝不参与"删除"决策**。

背景（数据安全缺陷，`serializers.py` 的 `_merge_method_ids` / `_sync_method_bridges`）：

    merged = direct | cascaded          # 旧实现把两者混成一个集合
    self._sync_method_bridges(p, merged)  # 而后者是**差量同步**（先删 existing - desired）

  ⇒ `desired` 一旦小于 `existing`，**既有方法关联会被真删**。
  ⇒ 而 `research_goal_ids` / `application_ids` 是"**一次性级联入口**"（后端根本没有
    Product↔Goal / Product↔Application 的桥表），语义上只该"**追加**"，绝不该"收敛"。
  ⇒ 一旦调用方**只传 goal/app、不传 method_ids**，`direct` 为空 ⇒ `desired` 退化为
    **纯级联集** ⇒ 不属于该 goal 的既有方法关联被**静默真删**。

本文件钉死修复后的目标语义（三种提交组合）：

  ① 只传 research_goal_ids / application_ids ⇒ **既有方法关联一个都不能少**，
     goal/app 下的方法被**追加**。（删除决策的唯一依据是 method_ids，而它未给出）
  ② 只传 method_ids ⇒ 维持既有**差量同步**：删掉不在 desired 里的、加上新的。
  ③ 两者都传 ⇒ method_ids 表达 **desired 全集**并照常差量同步；goal/app 级联出的方法
     **必须被包含在内**（不在 method_ids 里就自动补上），但级联项**自身不参与删除**。

⚠️ 与 `test_product_goal_cascade_probe.py` 的分工：那个文件是「取证」，记录 *1333ccc 当时*
   的真实行为（其中两条记录的正是本缺陷）；本文件是「契约」，断言**修复后**的正确行为。
"""
from django.test import TestCase

from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import Method
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


class GoalCascadeIsAppendOnlyTest(TestCase):
    """①②③ 三种提交组合的目标语义。"""

    def setUp(self):
        self.goal = ResearchGoalFactory(name='RNA Analysis')
        self.other_goal = ResearchGoalFactory(name='Click Chemistry')
        self.app_a = ApplicationFactory(name='RNA Labeling', research_goal=self.goal)
        self.app_b = ApplicationFactory(name='Sequencing', research_goal=self.goal)
        self.app_other = ApplicationFactory(name='Click', research_goal=self.other_goal)
        # 三个方法：两个属 goal，一个属 other_goal（对照组）
        self.m_a1 = MethodFactory(name='CuAAC', application=self.app_a)
        self.m_a2 = MethodFactory(name='NHS-Ester', application=self.app_b)
        self.m_other = MethodFactory(name='SPAAC', application=self.app_other)

    def _save(self, product, data):
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        return serializer

    # ── ① 只传 goal/app：既有方法关联零丢失 + 级联追加 ──────────────────────────

    def test_goal_only_preserves_every_existing_method(self):
        """★核心安全不变式：只传 research_goal_ids ⇒ 既有方法关联**一条都不许少**。

        这是本缺陷的直接对立面：旧实现会把 `m_other`（不属于该 goal）真删掉。
        """
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)
        before = _pm_ids(product)
        self.assertEqual(before, [self.m_other.id])

        self._save(product, {'research_goal_ids': [self.goal.id]})

        after = _pm_ids(product)
        self.assertTrue(
            ProductMethod.objects.filter(product=product, method=self.m_other).exists(),
            f'只传 goal_ids 却删掉了既有方法关联 before={before} after={after}',
        )
        self.assertEqual(after, sorted([self.m_a1.id, self.m_a2.id, self.m_other.id]))

    def test_application_only_preserves_every_existing_method(self):
        """同理：只传 application_ids 也是纯追加，不许删既有桥。"""
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)

        self._save(product, {'application_ids': [self.app_a.id]})

        self.assertEqual(_pm_ids(product), sorted([self.m_a1.id, self.m_other.id]))

    def test_goal_only_is_idempotent_and_never_shrinks_across_repeats(self):
        """★ 反复提交同一个 goal：既不丢已有、也不产生重复桥（幂等）。"""
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)

        for _ in range(3):
            self._save(product, {'research_goal_ids': [self.goal.id]})

        after = _pm_ids(product)
        self.assertEqual(after, sorted([self.m_a1.id, self.m_a2.id, self.m_other.id]))
        # 无重复行（ProductMethod 唯一约束之外的"重复创建"也会被这里抓到：计数必须相等）
        self.assertEqual(
            ProductMethod.objects.filter(product=product).count(), len(after)
        )

    def test_empty_goal_ids_does_not_clear_method_chain(self):
        """★ 传 `research_goal_ids: []`（显式清空）**不得**清空整条方法链。

        旧行为：cascaded 与 direct 皆空 ⇒ desired 为空集 ⇒ 整链被删。
        修复后：method_ids 未给出 ⇒ **无删除决策依据** ⇒ 一条都不删。
        """
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)
        ProductMethodFactory(product=product, method=self.m_a1)
        before = _pm_ids(product)

        self._save(product, {'research_goal_ids': [], 'application_ids': []})

        self.assertEqual(
            _pm_ids(product), before,
            '传空 goal/app 数组只是"本次不追加任何方法"，不等于"清空方法链"',
        )

    # ── ② 只传 method_ids：既有差量同步语义必须原样保留 ────────────────────────

    def test_method_ids_only_still_removes_and_adds(self):
        """★ 不得把修复做成"永远不删"：只传 method_ids 时差量同步照旧生效。

        这是防"过度修复"的护栏 —— 若有人把 `_sync_method_bridges` 改成只增不删，
        本用例会红。
        """
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)
        ProductMethodFactory(product=product, method=self.m_a1)

        self._save(product, {'method_ids': [self.m_a2.id]})

        self.assertEqual(_pm_ids(product), [self.m_a2.id])

    def test_method_ids_empty_list_still_clears_chain(self):
        """`method_ids: []` 仍是"显式清空全链"（与 goal/app 的 [] 语义**刻意不同**）。"""
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)

        self._save(product, {'method_ids': []})

        self.assertEqual(_pm_ids(product), [])

    # ── ③ 两者都传：method_ids 是 desired 全集；级联项必须被加回 ────────────────

    def test_cascaded_method_absent_from_method_ids_is_added_back(self):
        """★ 冲突取舍：级联出的 `m_a1` 不在 method_ids 里 ⇒ **加回**（安全优先）。

        goal/app 是显式意图，若允许它被 method_ids 悄悄否决，用户勾选 goal 却发现
        方法没进来 ⇒ 静默失灵。故级联项一律并入最终结果。
        """
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)

        self._save(product, {
            'method_ids': [self.m_other.id],       # 只显式要了 m_other
            'research_goal_ids': [self.goal.id],   # 但 goal 牵连出 m_a1 / m_a2
        })

        self.assertEqual(
            _pm_ids(product), sorted([self.m_a1.id, self.m_a2.id, self.m_other.id])
        )

    def test_method_ids_still_governs_deletion_even_when_goal_present(self):
        """★ 冲突取舍的另一面：删除决策**只**看 method_ids，级联项不阻止删除。

        `m_other` 既不在 method_ids、也不在任何所选 goal/app 下 ⇒ 应当被删。
        （若级联项也进入删除基准，这条会红 —— 那说明修复把"删除权"错给了级联。）
        """
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)
        ProductMethodFactory(product=product, method=self.m_a2)

        self._save(product, {
            'method_ids': [self.m_a2.id],
            'research_goal_ids': [self.goal.id],
        })

        # m_a1 由 goal 级联补上；m_a2 保留（显式 desired）；m_other 被删（不在 desired）
        self.assertEqual(_pm_ids(product), sorted([self.m_a1.id, self.m_a2.id]))
        self.assertFalse(
            ProductMethod.objects.filter(product=product, method=self.m_other).exists(),
            'method_ids 表达的 desired 全集仍应驱动删除 —— 修复不能退化成"只增不删"',
        )

    def test_cascaded_method_keeps_its_bridge_row_instead_of_delete_recreate(self):
        """★ 级联项必须**原地保留**（行 id 不变），不得被"先删后建"。

        场景：该方法既属所选 goal（会被级联补上）、又被显式的 method_ids 移出。
        若实现先把 `existing - desired` 删掉再补回，同一条桥会经历
        「DELETE → INSERT」⇒ ProductMethod 行 id 变化、无谓的 created/updated 刷新。
        （实测确认：`ProductMethodRelation` 指向 Product/Method 而非 ProductMethod，
        故不会级联删数据，但行 id 抖动仍是可避免的副作用。）
        """
        product = ProductFactory()
        bridge = ProductMethodFactory(product=product, method=self.m_a1)
        bridge_pk = bridge.pk
        ProductMethodFactory(product=product, method=self.m_other)

        self._save(product, {
            'method_ids': [self.m_other.id],       # 显式移出 m_a1
            'research_goal_ids': [self.goal.id],   # 但 m_a1 属该 goal ⇒ 仍应保留
        })

        # m_a1 仍在链上，且**沿用原桥行**（未删后重建）
        still = ProductMethod.objects.filter(product=product, method=self.m_a1)
        self.assertEqual(still.count(), 1, 'm_a1 应恰好保留一条桥（无重复）')
        self.assertEqual(
            still.first().pk, bridge_pk,
            'm_a1 的桥行被删后重建（pk 变化）—— 应原地保留',
        )

    def test_cascade_does_not_introduce_nonexistent_methods(self):
        """级联集必须只含真实存在的 Method（不能把脏 id 写进桥表）。"""
        product = ProductFactory()

        self._save(product, {
            'method_ids': [999999],                  # 不存在的 method
            'research_goal_ids': [self.goal.id],
        })

        after = _pm_ids(product)
        self.assertEqual(after, sorted([self.m_a1.id, self.m_a2.id]))
        for mid in after:
            self.assertTrue(Method.objects.filter(id=mid).exists())


class InheritedProtocolRowsSurviveGoalOnlySubmitTest(TestCase):
    """只传 goal/app 时，`_refresh_inherited_bridges` 的 INHERITED 收敛不得吃掉数据。

    `chain_specified` 仍把 goal/app 计入"显式给出方法链"，故只传 goal/app 时会走
    `ProductProtocol(INHERITED)` 的 prune 分支。本组用例钉死其安全性：
    **仍在派生集内的 INHERITED 行必须一条不少**（方法链只增不减 ⇒ 派生集只增不减）。

    注：这里**直接预置** INHERITED 行而不走 `recompute_product` —— 后者有
    `is_evidence_free(fused) ⇒ continue` 的"零证据不落库"门槛，factory 造出的
    产品/协议组合通常拿不到分数，行根本不会写入（实测确认）。本用例要验证的
    是"prune 分支会不会误删"，与打分逻辑无关，故绕开。
    """

    def setUp(self):
        from apps.bridges.models import MethodProtocol, ProductProtocol
        from apps.knowledge.tests.factories import ProtocolFactory
        self.goal = ResearchGoalFactory(name='RNA Analysis')
        self.app = ApplicationFactory(name='RNA Labeling', research_goal=self.goal)
        self.m_goal = MethodFactory(name='CuAAC', application=self.app)
        self.other_goal = ResearchGoalFactory(name='Click Chemistry')
        self.other_app = ApplicationFactory(name='Click', research_goal=self.other_goal)
        self.m_other = MethodFactory(name='SPAAC', application=self.other_app)
        self.proto_of_goal = ProtocolFactory(name='Goal Protocol')
        self.proto_of_other = ProtocolFactory(name='Other Protocol')
        MethodProtocol.objects.create(method=self.m_goal, protocol=self.proto_of_goal)
        MethodProtocol.objects.create(method=self.m_other, protocol=self.proto_of_other)
        self._PP = ProductProtocol

    def test_inherited_rows_derived_from_kept_methods_are_not_pruned(self):
        """既有方法对应的 INHERITED 协议行，在只传 goal/app 后必须全部存活。"""
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_other)
        self._PP.objects.create(
            product=product, protocol=self.proto_of_other,
            link_source=self._PP.LinkSource.INHERITED,
        )
        before = sorted(
            self._PP.objects.filter(
                product=product, link_source=self._PP.LinkSource.INHERITED,
            ).values_list('protocol_id', flat=True)
        )
        self.assertEqual(before, [self.proto_of_other.id], '前置条件：既有 1 条 INHERITED 行')

        serializer = ProductCreateUpdateSerializer(
            product, data={'research_goal_ids': [self.goal.id]}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        after = sorted(
            self._PP.objects.filter(
                product=product, link_source=self._PP.LinkSource.INHERITED,
            ).values_list('protocol_id', flat=True)
        )
        self.assertTrue(
            set(before).issubset(set(after)),
            f'只传 goal/app 把既有 INHERITED 协议行删掉了 before={before} after={after}',
        )


    def test_explicit_method_ids_still_prunes_stale_inherited_rows(self):
            """反向护栏：显式传 method_ids 时，**INHERITED 收敛仍须照常生效**。

            2026-10-17 把 `chain_specified` 收窄为只认 method_ids。若有人把它改成恒False
            （或把 prune 分支整体删掉），本用例会红——孤儿 INHERITED 行将永远堆积。
            这里构造一条"已不可达"的孤儿行：产品只关联 m_other，但库里留了一条指向
            m_goal 派生协议的 INHERITED 行。
            """
            product = ProductFactory()
            ProductMethodFactory(product=product, method=self.m_other)
            stale = self._PP.objects.create(
                product=product, protocol=self.proto_of_goal,   # 来自 m_goal，产品并未关联它
                link_source=self._PP.LinkSource.INHERITED,
            )
            stale_pk = stale.pk

            self.assertTrue(
                self._PP.objects.filter(pk=stale_pk).exists(), '前置条件：孤儿 INHERITED 行存在')

            serializer = ProductCreateUpdateSerializer(
                product, data={'method_ids': [self.m_other.id]}, partial=True)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            serializer.save()

            self.assertFalse(
                self._PP.objects.filter(pk=stale_pk).exists(),
                '显式给出 method_ids 时，可达的派生集应收敛、孤儿 INHERITED 行应被清理'
            )


class NoChainFieldPreservesEverythingTest(TestCase):
    """完全不碰方法链字段的普通字段编辑，不得动方法链。"""

    def setUp(self):
        self.goal = ResearchGoalFactory(name='RNA Analysis')
        self.app = ApplicationFactory(name='RNA Labeling', research_goal=self.goal)
        self.m_a = MethodFactory(name='CuAAC', application=self.app)
        self.other_goal = ResearchGoalFactory(name='Click Chemistry')
        self.other_app = ApplicationFactory(name='Click', research_goal=self.other_goal)
        self.m_other = MethodFactory(name='SPAAC', application=self.other_app)

    def test_updating_unrelated_field_keeps_method_chain(self):
        """回归护栏：改个 name 之类，既有方法关联一条都不能少。"""
        product = ProductFactory()
        ProductMethodFactory(product=product, method=self.m_a)
        ProductMethodFactory(product=product, method=self.m_other)
        before = _pm_ids(product)

        serializer = ProductCreateUpdateSerializer(
            product, data={'name': 'Renamed Product'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(_pm_ids(product), before)