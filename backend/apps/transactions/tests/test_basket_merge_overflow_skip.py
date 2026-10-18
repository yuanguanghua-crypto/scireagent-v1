"""`POST /basket/merge` 超上限（叠加后 > 999）行为：**跳过 + 明细回传**。

设计背景（本次改动的决策依据，非修 bug）：

`MergeBasketView.post` 的循环体里，「数量/ID 非法」四类情况一律走**跳过**
语义（`skipped_count += 1` + 追加 `skipped_items` + `continue`），只有
「叠加后超过 `max_line_quantity`(999)」这一条跳出体系去`raise ValidationError`
⇒ 整条 400。

前端 `stores/basket.js` 的 `mergeLocalBasket` 提交的是**整个购物车列表**，
于是「5 件里1 件超限」的实际后果是：

  - 整条 400 ⇒ 走 catch 分支 ⇒ **5 件一件都合并不进去**，
    全部留在 localStorage 等重试；
  - 重试仍是同样 payload ⇒同样 400 ⇒**死循环，永久合并不了**。

⚠️ 以上是**修复前的实测结论**（5 个 SKU，第1 个预置 950、提交 100
⇒ 1050 > 999）：

    HTTP 400
    {"success": false, "meta": {"error": {"code": "validation_error",
     "message": "items: 合并后数量将超过上限 999"}}}
    落库：只有预置的 sku=1 quantity=950 —— 其余 4 件**一件都没落库**
    同样 payload 重试第2 次：仍 400，落库仍只有那1 件

用户决策：改为「跳过该行 + 明细回传」，**不引入静默截断**（截断会让用户拿到
一个既非其请求值、也非原值的数量）。被跳过的行会留在 localStorage
（前端 `pruneMergedLocalItems` 只剔除已确认合并成功的行），用户可自行调整后
重试 —— 天然没有「下次再超限」的累积问题。

本文件锁定的契约：
  1. 5 件中 1 件超限 ⇒ **200**（不是 400）+ 其余 4 件真的合并成功
  2. `skipped === 1` 且 `skipped_items` 精确含被跳过的那一行
  3. `len(skipped_items) === skipped` 不变量
  4. 超限行**不得**改动已有行的数量（既不静默截断，也不叠加）
  5. ★ 重试语义：同样 payload 再提交仍是 200 + 仍 skipped（**不是 400**）
     —— 这条直接对应"死循环"根因
  6. 边界：叠加**正好 999** 必须成功合并（不误杀）
  7. 既有跳过路径（非法 sku_id / 非法 quantity）不得回归
  8. `skipped_items` 带 `reason`，前端据此区分「超上限」与「非法输入」
"""
import json

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Basket


class MergeBasketOverflowSkipTest(TestCase):
    """叠加超999 ⇒ 跳过 + 明细，而不是整条 400。"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.product = ProductFactory(name='PO', status='active')
        # 5 个不同 SKU —— 覆盖「5 件中 1 件超限」这个核心场景
        self.skus = [
            SKUFactory(product=self.product, sku_code=f'PO-S{i}') for i in range(5)
        ]
        self.client.force_authenticate(user=self.user)

    def _merge(self, payload):
        return self.client.post('/api/v1/basket/merge', payload, format='json')

    def _qty(self, sku):
        row = Basket.objects.filter(user=self.user, sku=sku).first()
        return row.quantity if row else None

    # ------------------------------------------------------------------
    # ★ 核心场景：5 件中 1 件叠加后超 999
    # ------------------------------------------------------------------

    def test_one_overflow_among_five_returns_200_and_merges_the_rest(self):
        """★ 本次改动的主要价值：1 件超限不该拖垮另外 4 件。

        修复前实测：整条 400，其余 4 件一件都没落库，且重试永远 400。
        """
        over_sku, ok_skus = self.skus[0], self.skus[1:]
        Basket.objects.create(
            user=self.user, product=self.product, sku=over_sku, quantity=950
        )

        resp = self._merge({'items': [
            {'sku_id': over_sku.id, 'quantity': 100},   # 950 + 100 = 1050 > 999
            {'sku_id': ok_skus[0].id, 'quantity': 2},
            {'sku_id': ok_skus[1].id, 'quantity': 3},
            {'sku_id': ok_skus[2].id, 'quantity': 4},
            {'sku_id': ok_skus[3].id, 'quantity': 5},
        ]})

        self.assertEqual(
            resp.status_code, 200,
            f'1 件超限不得让整条请求 400；实际响应体='
            f'{json.dumps(resp.json(), ensure_ascii=False, default=str)}',
        )
        data = resp.json()['data']

        # 其余 4 件必须真的合并进账户（不能整体回滚）
        self.assertEqual(data['merged'], 4, '4 件有效商品必须全部合并成功')
        for sku, want in zip(ok_skus, (2, 3, 4, 5)):
            self.assertEqual(
                self._qty(sku), want,
                f'sku={sku.sku_code} 必须已落库',
            )

        # 被跳过的那一行
        self.assertEqual(data['skipped'], 1)
        self.assertEqual(len(data['skipped_items']), 1)
        self.assertEqual(data['skipped_items'][0]['sku_id'], over_sku.id)
        self.assertEqual(data['skipped_items'][0]['quantity'], 100)

        # 超限行不得改动已有数量（既不静默截断，也不叠加）
        self.assertEqual(
            self._qty(over_sku), 950,
            '超限行必须原样保留既有数量 —— 截断会让用户拿到一个既非请求值'
            '也非原值的数量',
        )

        # 不变量：明细条数必须与计数一致（前端按明细剔除行）
        self.assertEqual(len(data['skipped_items']), data['skipped'])

    def test_merged_rows_persist_after_partial_skip(self):
        """部分跳过时成功的那部分必须**真的落库**（不能整体回滚）。"""
        over_sku = self.skus[0]
        Basket.objects.create(
            user=self.user, product=self.product, sku=over_sku, quantity=950
        )
        resp = self._merge({'items': [
            {'sku_id': over_sku.id, 'quantity': 100},
            {'sku_id': self.skus[1].id, 'quantity': 7},
        ]})
        self.assertEqual(resp.status_code, 200)
        # 账户里共 2 行：预置的 950（未动）+ 新合并的 7
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 2)
        self.assertEqual(self._qty(self.skus[1]), 7)

    # ------------------------------------------------------------------
    # ★ 重试语义 —— 直接对应"死循环"根因
    # ------------------------------------------------------------------

    def test_retry_same_payload_skips_again_instead_of_400(self):
        """★ 最重要的一条：被跳过的行留在 localStorage 后，再次提交**仍应被跳过**。

        修复前：同样 payload 第二次提交仍 400 ⇒ 前端 catch 分支 ⇒
        永远合并不了 ⇒ 死循环。

        修复后：200 + skipped=1（其余行正常合并），前端 `pruneMergedLocalItems`
        保留该行待重试，用户调整数量后可成功合并。
        """
        over_sku = self.skus[0]
        Basket.objects.create(
            user=self.user, product=self.product, sku=over_sku, quantity=950
        )
        payload = {'items': [
            {'sku_id': over_sku.id, 'quantity': 100},
            {'sku_id': self.skus[1].id, 'quantity': 2},
        ]}

        first = self._merge(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['data']['skipped'], 1)

        # ★ 重试：同样 payload，未做任何调整（用户还没来得及改）
        second = self._merge(payload)
        self.assertEqual(
            second.status_code, 200,
            '重试不得变成 400 —— 那正是死循环的根因',
        )
        data = second.json()['data']
        self.assertEqual(data['skipped'], 1, '未调整前，重试仍应被跳过')
        self.assertEqual(len(data['skipped_items']), 1)

        # 重试也不得叠加已有数量
        self.assertEqual(self._qty(over_sku), 950)

    def test_retry_after_user_lowers_quantity_succeeds(self):
        """用户把数量调低后重试 ⇒ 该行应成功合并（跳过方案不封死后路）。"""
        over_sku = self.skus[0]
        Basket.objects.create(
            user=self.user, product=self.product, sku=over_sku, quantity=950
        )
        self.assertEqual(
            self._merge({'items': [
                {'sku_id': over_sku.id, 'quantity': 100},
            ]}).status_code, 200,
        )

        # 用户看到"超上限"提示，把 100 调成 40 ⇒ 950 + 40 = 990 ≤ 999
        resp = self._merge({'items': [{'sku_id': over_sku.id, 'quantity': 40}]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['skipped'], 0)
        self.assertEqual(self._qty(over_sku), 990)

    # ------------------------------------------------------------------
    # 边界：叠加正好 999 必须成功（不误杀）
    # ------------------------------------------------------------------

    def test_accumulating_to_exactly_max_succeeds(self):
        """900 + 99 = 999 ⇒ 成功合并，不得被边界条件误伤。"""
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=900
        )
        resp = self._merge({'items': [{'sku_id': self.skus[0].id, 'quantity': 99}]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['merged'], 1)
        self.assertEqual(data['skipped'], 0)
        self.assertEqual(self._qty(self.skus[0]), 999)

    def test_accumulating_to_max_plus_one_is_skipped(self):
        """900 + 100 = 1000 ⇒ 超 1 个也要跳过（`>` 不是 `>=`）。"""
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=900
        )
        resp = self._merge({'items': [{'sku_id': self.skus[0].id, 'quantity': 100}]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['skipped'], 1)
        self.assertEqual(self._qty(self.skus[0]), 900)

    def test_new_line_at_max_needs_no_skip(self):
        """新建行 quantity=999（未叠加）⇒ 正常合并，超限检查不应误伤。"""
        resp = self._merge({'items': [{'sku_id': self.skus[0].id, 'quantity': 999}]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['merged'], 1)
        self.assertEqual(self._qty(self.skus[0]), 999)

    # ------------------------------------------------------------------
    # reason 字段 —— 可诊断性（向后兼容：只加字段，不改既有字段名/语义）
    # ------------------------------------------------------------------

    def test_overflow_skip_carries_distinguishable_reason(self):
        """超上限的跳过必须可与「非法输入」区分开，否则前端只能给出笼统提示。

        前端 `stores/basket.js` 的 `pruneMergedLocalItems` 只按 `sku_id` 匹配，
        多出 `reason` 字段对它无影响（已读码确认）。
        """
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=950
        )
        resp = self._merge({'items': [
            {'sku_id': self.skus[0].id, 'quantity': 100},   # 超上限
            {'sku_id': 99999999, 'quantity': 1},# SKU 不存在
        ]})
        self.assertEqual(resp.status_code, 200)
        rows = {r['sku_id']: r for r in resp.json()['data']['skipped_items']}
        self.assertEqual(len(rows), 2)

        overflow_reason = rows[self.skus[0].id]['reason']
        unknown_reason = rows[99999999]['reason']
        self.assertTrue(overflow_reason, '超限行必须带 reason')
        self.assertNotEqual(
            overflow_reason, unknown_reason,
            '「叠加超上限」与「SKU 不存在」必须是不同的 reason，'
            '否则前端无法给出针对性提示',
        )
        self.assertIn('999', str(overflow_reason), 'reason 应带上限值，便于诊断')

    def test_skipped_items_keeps_sku_id_and_quantity_keys(self):
        """向后兼容：既有键 `sku_id` / `quantity` 一字不能改（1ab7d0f 定的契约）。

        前端 `pruneMergedLocalItems` 用 `String(row?.sku_id)` 匹配本地副本，
        键名或语义变化会让「只剔除已合并行」失效 ⇒ 被跳过的行被误删。
        """
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=950
        )
        resp = self._merge({'items': [{'sku_id': self.skus[0].id, 'quantity': 100}]})
        row = resp.json()['data']['skipped_items'][0]
        self.assertEqual(row['sku_id'], self.skus[0].id)
        self.assertEqual(row['quantity'], 100)
        # 既有的 merged / skipped / skipped_items 字段名与语义不变
        data = resp.json()['data']
        for key in ('merged', 'skipped', 'skipped_items', 'items', 'total', 'count'):
            self.assertIn(key, data)

    # ------------------------------------------------------------------
    # 既有跳过路径不得回归
    # ------------------------------------------------------------------

    def test_unknown_sku_still_skipped_with_overflow_present(self):
        """非法 sku_id 仍走跳过（不是 400），且与超限行共存。"""
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=950
        )
        resp = self._merge({'items': [
            {'sku_id': self.skus[0].id, 'quantity': 100},
            {'sku_id': 99999999, 'quantity': 1},
            {'sku_id': self.skus[1].id, 'quantity': 3},
        ]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['merged'], 1)
        self.assertEqual(data['skipped'], 2)
        self.assertEqual(len(data['skipped_items']), 2)
        self.assertEqual(
            {r['sku_id'] for r in data['skipped_items']},
            {self.skus[0].id, 99999999},
        )

    def test_overflow_row_never_counted_as_merged(self):
        """超限行绝不能进 `merged` —— 前端据此判断哪些行可从本地副本剔除。

        若超限行误入 merged，前端会把它从 localStorage 剔除 ⇒ 该行既没合并
        进账户、也没留在本地 ⇒ 彻底丢失（1ab7d0f 修复的那类数据丢失）。
        """
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=950
        )
        resp = self._merge({'items': [
            {'sku_id': self.skus[0].id, 'quantity': 100},
            {'sku_id': self.skus[1].id, 'quantity': 1},
        ]})
        data = resp.json()['data']
        self.assertEqual(data['merged'], 1)
        self.assertEqual(data['skipped'], 1)
        self.assertNotIn(
            self.skus[0].id, [r['sku_id'] for r in data['skipped_items']][1:],
        )

    def test_response_count_reflects_committed_rows_only(self):
        """响应的 `count` / `items` 必须反映真实落库结果。

        预置行（950，未被改动）也在响应里 —— 它确实存在于账户购物车中，
        回传它是对的；要保证的是**超限请求没有虚增任何行/数量**。
        """
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=950
        )
        resp = self._merge({'items': [
            {'sku_id': self.skus[0].id, 'quantity': 100},
            {'sku_id': self.skus[1].id, 'quantity': 6},
        ]})
        data = resp.json()['data']
        self.assertEqual(data['count'], 2, '预置行 + 新合并行 = 2')
        quantities = {i['sku']: i['quantity'] for i in data['items']}
        self.assertEqual(
            quantities, {self.skus[0].id: 950, self.skus[1].id: 6},
            '超限行数量必须保持 950（未被截断、未被叠加）',
        )

    # ------------------------------------------------------------------
    # 鉴权门槛不回退
    # ------------------------------------------------------------------

    def test_overflow_path_still_requires_authentication(self):
        self.client.force_authenticate(user=None)
        resp = self._merge({'items': [{'sku_id': self.skus[0].id, 'quantity': 1}]})
        self.assertEqual(resp.status_code, 401)


class MergeBasketOverflowIsolationTest(TestCase):
    """超限**不得**污染同批次里其他行的合并结果（逐行隔离）。"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.product = ProductFactory(name='ISO', status='active')
        self.skus = [
            SKUFactory(product=self.product, sku_code=f'ISO-S{i}') for i in range(4)
        ]
        self.client.force_authenticate(user=self.user)

    def test_two_overflows_in_one_batch(self):
        """一批里2 件超限 ⇒ 其余 2 件照常合并，skipped=2。"""
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=950
        )
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[1], quantity=500
        )
        resp = self.client.post('/api/v1/basket/merge', {'items': [
            {'sku_id': self.skus[0].id, 'quantity': 100},  # 1050 > 999
            {'sku_id': self.skus[1].id, 'quantity': 500},  # 1000 > 999
            {'sku_id': self.skus[2].id, 'quantity': 1},
            {'sku_id': self.skus[3].id, 'quantity': 2},
        ]}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['merged'], 2)
        self.assertEqual(data['skipped'], 2)
        self.assertEqual(len(data['skipped_items']), data['skipped'])
        self.assertEqual(
            {r['sku_id'] for r in data['skipped_items']},
            {self.skus[0].id, self.skus[1].id},
        )
        rows = {b.sku_id: b.quantity for b in
                Basket.objects.filter(user=self.user)}
        self.assertEqual(
            rows,
            {self.skus[0].id: 950, self.skus[1].id: 500,
             self.skus[2].id: 1, self.skus[3].id: 2},
            '两条超限行的既有数量都不得被改动',
        )

    def test_overflow_does_not_abort_following_rows(self):
        """超限行之后的行仍必须被处理（修复前 raise 会中止整个循环）。"""
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.skus[0], quantity=999
        )
        resp = self.client.post('/api/v1/basket/merge', {'items': [
            {'sku_id': self.skus[0].id, 'quantity': 1},   # 999 + 1 = 1000 > 999
            {'sku_id': self.skus[1].id, 'quantity': 11},
            {'sku_id': self.skus[2].id, 'quantity': 22},
        ]}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['merged'], 2, '超限行之后的 2 件必须照常合并')
        self.assertEqual(data['skipped'], 1)
        rows = {b.sku_id: b.quantity for b in
                Basket.objects.filter(user=self.user)}
        self.assertEqual(rows[self.skus[1].id], 11)
        self.assertEqual(rows[self.skus[2].id], 22)
        self.assertEqual(rows[self.skus[0].id], 999)


class MergeBasketSkippedItemNameTest(TestCase):
    """`skipped_items[].product_name` —— 让用户能认出「是哪件没合并」。

    背景（实测）：原 `skipped_items` 只有 `sku_id` / `quantity` / `reason`，
    前端只能提示「N 件未能合并」，用户既不知道是哪件，也无从手动补救
    （被跳过的行在真实链路上已彻底消失，见
    `frontend/e2e/basket-merge-over-limit.spec.cjs` 的 RT5）。

    本次契约（只**新增**字段，不改既有字段名与语义）：
      - 能拿到 SKU 的分支 ⇒ `product_name` == `sku.product.name`
        （`sku` 由 `select_related('product')` 取出，零额外查询）
      - 拿不到 SKU 的分支 ⇒ `product_name` 为 `None`，但**键必须存在**
        （前端无需判断键的有无，直接 `|| fallback`）
    """

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.product = ProductFactory(
            name='GelRed Nucleic Acid Stain', status='active')
        self.over_sku = SKUFactory(product=self.product, sku_code='NAME-OVER')
        self.ok_sku = SKUFactory(product=self.product, sku_code='NAME-OK')
        self.client.force_authenticate(user=self.user)

    def _merge(self, payload):
        return self.client.post('/api/v1/basket/merge', payload, format='json')

    def test_overflow_skip_carries_product_name(self):
        """超 999 被跳过时，前端必须能拿到商品名（用户据此识别是哪件）。"""
        Basket.objects.create(
            user=self.user, product=self.product,
            sku=self.over_sku, quantity=998,
        )
        resp = self._merge({'items': [
            {'sku_id': self.over_sku.id, 'quantity': 2},   # 998 + 2 = 1000 > 999
        ]})
        self.assertEqual(resp.status_code, 200)
        row = resp.json()['data']['skipped_items'][0]
        self.assertEqual(
            row['product_name'], 'GelRed Nucleic Acid Stain',
            '超限跳过必须回传商品名，否则用户无法识别是哪件',
        )
        # 既有契约字段一字不改
        self.assertEqual(row['sku_id'], self.over_sku.id)
        self.assertEqual(row['quantity'], 2)

    def test_unknown_sku_skip_has_product_name_key_set_to_none(self):
        """查不到 SKU 时无名字可给 ⇒ 值为 None，但**键必须在**。"""
        resp = self._merge({'items': [{'sku_id': 99999999, 'quantity': 1}]})
        self.assertEqual(resp.status_code, 200)
        row = resp.json()['data']['skipped_items'][0]
        self.assertIn(
            'product_name', row,
            '键必须存在：前端不判断键有无，只判断值是否为空',
        )
        self.assertIsNone(row['product_name'])

    def test_every_skipped_row_has_product_name_key(self):
        """混批（能查到 / 查不到 SKU）⇒ 每条跳过明细都带同一个键集合。"""
        Basket.objects.create(
            user=self.user, product=self.product,
            sku=self.over_sku, quantity=998,
        )
        resp = self._merge({'items': [
            {'sku_id': self.over_sku.id, 'quantity': 2},   # 超限
            {'sku_id': 99999999, 'quantity': 1},           # SKU 不存在
            {'sku_id': self.ok_sku.id, 'quantity': 3},     # 正常合并
        ]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        rows = data['skipped_items']
        self.assertEqual(len(rows), data['skipped'])
        self.assertEqual(data['skipped'], 2)
        self.assertEqual(data['merged'], 1)
        for row in rows:
            self.assertIn('product_name', row)
            self.assertIn('sku_id', row)
            self.assertIn('quantity', row)
            self.assertIn('reason', row)
        names = {r['sku_id']: r['product_name'] for r in rows}
        self.assertEqual(names[self.over_sku.id], 'GelRed Nucleic Acid Stain')
        self.assertIsNone(names[99999999])

    def test_merged_plus_skipped_equals_submitted_rows(self):
        """加了字段也不得影响 `merged + skipped == 提交行数` 这一不变量。"""
        Basket.objects.create(
            user=self.user, product=self.product,
            sku=self.over_sku, quantity=999,
        )
        resp = self._merge({'items': [
            {'sku_id': self.over_sku.id, 'quantity': 1},   # 999 + 1 = 1000 > 999
            {'sku_id': self.ok_sku.id, 'quantity': 1},
            {'sku_id': 99999999, 'quantity': 1},
        ]})
        data = resp.json()['data']
        self.assertEqual(data['merged'] + data['skipped'], 3)
        self.assertEqual(len(data['skipped_items']), data['skipped'])