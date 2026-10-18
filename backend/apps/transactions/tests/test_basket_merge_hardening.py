"""P1 缺陷回归：`POST /basket/merge` 可被任意已登录用户打成 500 并写入脏数据。

缺陷背景（本次实测，traceback 见交付记录）：

`MergeBasketSerializer.items` 用的是**无 child 约束**的 `DictField()`
（`basket_serializers.py:65`），items 元素可以是任意 key-value 组合；
`MergeBasketView.post` 的循环体（`basket_views.py:217-239`）只捕获
`SKU.DoesNotExist`，于是四类输入直接冒到 500：

  A ``{"sku_id":"abc","quantity":"not-a-number"}``
      → `basket_views.py:224` `SKU.objects.get(id='abc')` 在 Django
        `IntegerField.get_prep_value` 里 `int('abc')` ⇒ ``ValueError``
  B ``{"sku_id":<合法int>,"quantity":"abc"}``
      → `basket_views.py:233` 裸调用 ``int('abc')`` ⇒ ``ValueError``
  C ``{"sku_id":"not-an-int","quantity":1}``
      → `basket_views.py:224` ⇒ ``ValueError: Field 'id' expected a number``
  D ``{"sku_id":<合法int>,"quantity":99999999999999999999}``
      → ``int()`` 对 Python 大整数**不抛**，炸在 `basket_views.py:228`
        ``get_or_create`` 的 DB 写入 ⇒ ``OverflowError: Python int too large
        to convert to SQLite INTEGER``

⚠️ D 证明了「超大整数由 DRF 层抛 ValidationError」的猜测是错的：真正的约束
在 DB 驱动层，因此兜底必须覆盖 `SKU.get` **和** `get_or_create` 整段。

同时实测到三类脏数据（200 却落库）：
  - ``quantity=-999999``  ⇒ 购物车合计变成负数（实测 total="-99989900.01"）
  - ``quantity=100000``   ⇒ 绕过 `AddToBasketSerializer` 的 ``max_value=999``
  - 累加无上限：900 + 900 ⇒ 落库 1800

铁证这是疏漏而非设计：同文件 `:49`（AddToBasket）与 `:59`
（UpdateBasketItem）都写了 ``IntegerField(min_value=1, max_value=999)``，
唯独 merge 的 items 是裸 ``DictField()``。

触发门槛只需 ``IsAuthenticated``（实测匿名 401、登录即 500/脏数据），
不需要管理员权限。

另：本文件顺带补上两个**零覆盖**端点的测试 ——
``PATCH /basket/items/<pk>`` 与 ``DELETE /basket/items/<pk>/delete``，
它们的归属校验分支（`basket_views.py:148-160` / `:183-196`）此前完全没被测到。

后续补充（跳过明细契约）：``MergeBasketView`` 的响应体除``merged`` / ``skipped``
计数外，还回传 ``skipped_items`` 明细（``[{'sku_id':…, 'quantity':…}]``）。
起因是前后端契约缺口：前端 ``stores/basket.js`` 的 ``mergeLocalBasket`` 原先
无条件 ``localStorage.removeItem(LOCAL_STORAGE_KEY)``，部分跳过时把**没合并成功**
的行一并抹掉 ⇒ 既没进账户、也没留在本地，彻底丢失。只有计数时无法定位是哪几行，
故必须回传明细，前端才能"只剔除已合并成功的行"。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Basket


class MergeBasketInputHardeningTest(TestCase):
    """merge 端点的输入校验：非法输入必须是 400，绝不能是 500。"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.product = ProductFactory(name='P', status='active')
        self.sku = SKUFactory(product=self.product, sku_code='SKU-H1')
        self.client.force_authenticate(user=self.user)

    def _merge(self, payload):
        return self.client.post('/api/v1/basket/merge', payload, format='json')

    # ------------------------------------------------------------------
    # 四类实测 500 —— 修复前每一条都会让未捕获异常冒到顶层
    # ------------------------------------------------------------------

    def test_case_a_non_numeric_sku_id_and_quantity_rejected(self):
        """A: sku_id 与 quantity 都非数字 ⇒ ValueError@SKU.get（:224）。"""
        resp = self._merge({'items': [{'sku_id': 'abc', 'quantity': 'not-a-number'}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 0)

    def test_case_b_numeric_sku_id_with_non_numeric_quantity_rejected(self):
        """B: sku_id 合法但 quantity 非数字 ⇒ ValueError@int()（:233）。"""
        resp = self._merge({'items': [{'sku_id': self.sku.id, 'quantity': 'abc'}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 0)

    def test_case_c_unparseable_sku_id_rejected(self):
        """C: sku_id 为不可转整数的字符串 ⇒ ValueError@SKU.get（:224）。"""
        resp = self._merge({'items': [{'sku_id': 'not-an-int', 'quantity': 1}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 0)

    def test_case_d_huge_integer_quantity_rejected(self):
        """D: quantity 超大整数 ⇒ OverflowError@get_or_create（:228），非 DRF 层。"""
        resp = self._merge(
            {'items': [{'sku_id': self.sku.id, 'quantity': 99999999999999999999}]}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 0)

    # ------------------------------------------------------------------
    # quantity 边界 —— 与 AddToBasket(:49) / UpdateBasketItem(:59) 对齐
    # ------------------------------------------------------------------

    def test_quantity_below_min_rejected(self):
        """quantity=-1：负数会算出负金额（实测 total 变负）。"""
        resp = self._merge({'items': [{'sku_id': self.sku.id, 'quantity': -1}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 0)

    def test_quantity_zero_rejected(self):
        """quantity=0：ListField(child=...) 默认 required，0 也低于 min_value=1。"""
        resp = self._merge({'items': [{'sku_id': self.sku.id, 'quantity': 0}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 0)

    def test_quantity_above_max_rejected(self):
        """quantity=1000：绕过 max_value=999（实测可落库 100000）。"""
        resp = self._merge({'items': [{'sku_id': self.sku.id, 'quantity': 1000}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 0)

    def test_boundary_values_accepted(self):
        """边界内取值必须仍能合并 —— 防止把合法请求一起打回。"""
        for qty in (1, 999):
            Basket.objects.filter(user=self.user).delete()
            resp = self._merge({'items': [{'sku_id': self.sku.id, 'quantity': qty}]})
            self.assertEqual(resp.status_code, 200, f'quantity={qty} 应被接受')
            self.assertEqual(
                Basket.objects.get(user=self.user, sku=self.sku).quantity, qty
            )

    # ------------------------------------------------------------------
    # 正常路径不回归
    # ------------------------------------------------------------------

    def test_valid_merge_still_succeeds_with_correct_count(self):
        """合法 guest 购物车合并成功，merged_count 正确。"""
        resp = self._merge(
            {'items': [
                {'sku_id': self.sku.id, 'quantity': 3},
                {'sku_id': self.sku.id, 'quantity': 2},
            ]}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['merged'], 2)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['items'][0]['quantity'], 5, '叠加语义：3 + 2 = 5')

    def test_merge_reports_skipped_count_for_unknown_sku(self):
        """⚠️ 部分失败必须**可感知**：不存在的 SKU 被跳过时要在响应里体现条数。

        这与既有 `SKU.DoesNotExist → continue` 的风格一致，但静默 continue
        会让前端以为「全部合并成功」。
        """
        resp = self._merge({'items': [
            {'sku_id': self.sku.id, 'quantity': 2},
            {'sku_id': 99999999, 'quantity': 1},
        ]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['merged'], 1, '合法的那条应合并成功')
        self.assertEqual(data['skipped'], 1, '跳过的条数必须回传给前端')

    # ------------------------------------------------------------------
    # skipped_items 明细 —— 前端"只清成功行"的**前置条件**
    # ------------------------------------------------------------------

    def test_merge_response_carries_skipped_items_field(self):
        """⚠️ 字段名实测为 `skipped_items`（不是 skipped_count），且必须始终存在。

        前端 `stores/basket.js` 的 mergeLocalBasket 依赖它区分「哪些行没合并」：
        只有 `skipped` 计数时无法定位被跳过的行，只能整键清 localStorage，
        于是跳过的那批既没进账户、也没留在本地，彻底丢失。
        """
        resp = self._merge({'items': [{'sku_id': self.sku.id, 'quantity': 1}]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('skipped_items', data, '全成功时也必须回传该字段（空列表）')
        self.assertEqual(data['skipped_items'], [], '全成功 ⇒ 无跳过明细')
        self.assertEqual(data['skipped'], 0)

    def test_skipped_items_identifies_which_rows_failed(self):
        """部分跳过时，明细必须精确指出**是哪几个 sku** 没合并。"""
        resp = self._merge({'items': [
            {'sku_id': self.sku.id, 'quantity': 2},   # 成功
            {'sku_id': 99999999, 'quantity': 1},      # 跳过：不存在的 SKU
            {'sku_id': 88888888, 'quantity': 5},      # 跳过：不存在的 SKU
        ]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['merged'], 1)
        self.assertEqual(data['skipped'], 2)
        self.assertEqual(len(data['skipped_items']), 2, '明细条数必须与 skipped 一致')

        failed_skus = {row['sku_id'] for row in data['skipped_items']}
        self.assertEqual(failed_skus, {99999999, 88888888})
        self.assertNotIn(
            self.sku.id, failed_skus,
            '合并成功的行绝不能出现在跳过明细里——否则前端会把它从本地副本剔除，'
            '导致下次重试时该行被二次叠加（数量翻倍）',
        )
        # 明细必须带 quantity，前端才能在提示里说清丢了什么
        for row in data['skipped_items']:
            self.assertIn('sku_id', row)
            self.assertIn('quantity', row)

    def test_skipped_items_count_always_matches_skipped_counter(self):
        """不变量：`len(skipped_items) === skipped`。前端按明细剔除行，两者不一致会误删。"""
        resp = self._merge({'items': [
            {'sku_id': self.sku.id, 'quantity': 1},
            {'sku_id': 99999999, 'quantity': 1},
            {'sku_id': 77777777, 'quantity': 1},
        ]})
        data = resp.json()['data']
        self.assertEqual(data['skipped'], len(data['skipped_items']))

    def test_merged_rows_are_actually_written_to_db(self):
        """部分跳过时，成功的那部分必须**真的落库**（不能整体回滚）。"""
        resp = self._merge({'items': [
            {'sku_id': self.sku.id, 'quantity': 4},
            {'sku_id': 99999999, 'quantity': 3},
        ]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            Basket.objects.get(user=self.user, sku=self.sku).quantity, 4,
            '合法行必须已合并进账户',
        )

    def test_merge_accumulates_up_to_max_without_exceeding(self):
        """叠加后不得超过 max_value=999（修复前 900 + 900 = 1800 可落库）。"""
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.sku, quantity=900
        )
        resp = self._merge({'items': [{'sku_id': self.sku.id, 'quantity': 900}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            Basket.objects.get(user=self.user, sku=self.sku).quantity, 900,
            '被拒的请求不得改动已有行的数量',
        )

    def test_merge_still_requires_authentication(self):
        """鉴权门槛不回退：匿名仍是 401。"""
        self.client.force_authenticate(user=None)
        resp = self._merge({'items': [{'sku_id': self.sku.id, 'quantity': 1}]})
        self.assertEqual(resp.status_code, 401)


class BasketItemOwnershipTest(TestCase):
    """顺带补零覆盖：`PATCH /basket/items/<pk>` 与 `DELETE .../delete`。

    这两个端点的归属校验分支（`basket_views.py:148-160` / `:183-196`）
    此前完全没有测试，任何人可改/删他人购物车行都不会被发现。
    """

    def setUp(self):
        self.client = APIClient()
        self.owner = UserFactory()
        self.stranger = UserFactory()
        self.product = ProductFactory(name='P', status='active')
        self.sku = SKUFactory(product=self.product, sku_code='SKU-O1')
        self.item = Basket.objects.create(
            user=self.owner, product=self.product, sku=self.sku, quantity=2
        )

    def _patch(self, pk, payload, **extra):
        return self.client.patch(
            f'/api/v1/basket/items/{pk}', payload, format='json', **extra
        )

    def _delete(self, pk, **extra):
        return self.client.delete(f'/api/v1/basket/items/{pk}/delete', **extra)

    # ---------------- PATCH ----------------

    def test_owner_can_update_quantity(self):
        """happy path：本人改自己的行，数量被更新。"""
        self.client.force_authenticate(user=self.owner)
        resp = self._patch(self.item.pk, {'quantity': 7})
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 7)

    def test_stranger_cannot_update_others_item(self):
        """越权：他人不得修改 ⇒ 404 且数量不变。"""
        self.client.force_authenticate(user=self.stranger)
        resp = self._patch(self.item.pk, {'quantity': 999})
        self.assertEqual(resp.status_code, 404)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 2, '越权请求不得改动数量')

    def test_anonymous_with_wrong_session_key_cannot_update(self):
        """越权：匿名 + 错误/缺失 X-Session-Key ⇒ 404。"""
        resp = self._patch(self.item.pk, {'quantity': 999})
        self.assertEqual(resp.status_code, 404)
        resp = self._patch(
            self.item.pk, {'quantity': 999}, HTTP_X_SESSION_KEY='someone-elses-key'
        )
        self.assertEqual(resp.status_code, 404)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 2)

    def test_patch_rejects_out_of_range_quantity(self):
        """PATCH 的 quantity 约束（:59 min1/max999）同样生效。"""
        self.client.force_authenticate(user=self.owner)
        for bad in (-1, 0, 1000):
            resp = self._patch(self.item.pk, {'quantity': bad})
            self.assertEqual(resp.status_code, 400, f'quantity={bad} 应被拒')
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 2)

    def test_patch_missing_item_returns_404(self):
        """不存在的 pk ⇒ 404（不是 500）。"""
        self.client.force_authenticate(user=self.owner)
        resp = self._patch(99999999, {'quantity': 1})
        self.assertEqual(resp.status_code, 404)

    # ---------------- DELETE ----------------

    def test_owner_can_delete_item(self):
        """happy path：本人删自己的行。"""
        self.client.force_authenticate(user=self.owner)
        resp = self._delete(self.item.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Basket.objects.filter(pk=self.item.pk).exists())

    def test_stranger_cannot_delete_others_item(self):
        """越权：他人不得删除 ⇒ 404 且行仍在。"""
        self.client.force_authenticate(user=self.stranger)
        resp = self._delete(self.item.pk)
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Basket.objects.filter(pk=self.item.pk).exists())

    def test_anonymous_with_wrong_session_key_cannot_delete(self):
        """越权：匿名 + 错误/缺失 X-Session-Key ⇒ 404 且行仍在。"""
        resp = self._delete(self.item.pk)
        self.assertEqual(resp.status_code, 404)
        resp = self._delete(self.item.pk, HTTP_X_SESSION_KEY='someone-elses-key')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Basket.objects.filter(pk=self.item.pk).exists())

    def test_guest_owner_can_manage_own_session_row(self):
        """匿名 happy path：X-Session-Key 匹配时可改可删自己的游客行。"""
        Basket.objects.create(
            user=None, product=self.product, sku=self.sku,
            quantity=1, session_key='guest-own-key',
        )
        row = Basket.objects.get(session_key='guest-own-key')

        resp = self._patch(row.pk, {'quantity': 5}, HTTP_X_SESSION_KEY='guest-own-key')
        self.assertEqual(resp.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.quantity, 5)

        resp = self._delete(row.pk, HTTP_X_SESSION_KEY='guest-own-key')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Basket.objects.filter(pk=row.pk).exists())

    def test_delete_missing_item_returns_404(self):
        """不存在的 pk ⇒ 404（不是 500）。"""
        self.client.force_authenticate(user=self.owner)
        resp = self._delete(99999999)
        self.assertEqual(resp.status_code, 404)
