"""A-152：回收站产品禁止被「静默发布」为 active（2026-11-18 / S4）。

背景（生产实测）：`Product` 有**两条互不相干的归档轴**

  · `archived`（布尔）—— 回收站轴。`DELETE` 置 True，`POST restore/` 置 False。
  · `status`（枚举）—— 业务状态轴。`POST archive/` 置 `archived`，`POST relist` 回 `active`。

旧实现里 `update()` 对两者**完全不校验**，于是 `PATCH {"status":"active"}` 能把一个
躺在回收站里的产品标记成「在售」—— 库里出现 `archived=True 且 status='active'` 的
**矛盾态**。这不是理论风险：生产 `product` 141 行里就有这样一批历史数据。

矛盾态的**实际危害**不是前台可见（`list` 默认 `exclude(archived=True)`，`retrieve`
对非 staff 抛 404），而是**任何忘记过滤 `archived` 的读取路径都会把它当成在售商品**。
已确实存在这样一条：收藏夹（A-258）的 `products` 内嵌 `ProductListSerializer` 时
不过滤 `archived` ⇒ 回收站产品按在售卡片展示。

本文件锁住的契约（**只拦新写入，不回溯清理历史**）：

1. `PATCH/PUT` 把 `archived=True` 的产品改成 `active` ⇒ **409**，且**库内不变**；
2. 同一次请求里的其它字段也**一并不落库**（不能"发布失败但改名成功"）；
3. 拒绝时**不写 UPDATE 审计**（validate 早于 perform_update，不会留幻影审计）；
4. 正向出路可达：`POST restore/` 之后 `PATCH {"status":"active"}` ⇒ 200（守卫不封路）；
5. 不误伤：回收站产品改 `name` / 改成 `draft` 仍然 200；在售产品照常发布。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import AuditLog, Product
from apps.commerce.tests.factories import ProductFactory

URL = '/api/v1/products/'


class RecycleBinPublishGuardTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.staff)
        # 回收站里的产品：archived=True，且 status 被历史数据留成了 active
        self.trashed = ProductFactory(
            name='Trashed Product', slug='trashed-product',
            status=Product.Status.ACTIVE, archived=True,
        )

    # ── 1. 主闸门：回收站产品不得 PATCH 成 active ──

    def test_patch_trashed_product_to_active_rejected(self):
        resp = self.client.patch(
            f'{URL}{self.trashed.pk}/', {'status': 'active'}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, resp.content[:400])
        self.trashed.refresh_from_db()
        self.assertTrue(self.trashed.archived, '★ 守卫把 archived 改了？本动作不该碰这一轴')
        self.assertEqual(self.trashed.status, Product.Status.ACTIVE)

    def test_put_trashed_product_to_active_rejected(self):
        resp = self.client.put(
            f'{URL}{self.trashed.pk}/',
            {'name': 'Trashed Product', 'slug': 'trashed-product', 'status': 'active'},
            format='json')

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, resp.content[:400])
        self.trashed.refresh_from_db()
        self.assertTrue(self.trashed.archived)

    # ── 2. 同请求的其它字段也不能落库（无部分写入）──

    def test_rejected_publish_does_not_leak_other_field_changes(self):
        resp = self.client.patch(
            f'{URL}{self.trashed.pk}/',
            {'status': 'active', 'name': 'Renamed While Publishing'},
            format='json')

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, resp.content[:400])
        self.trashed.refresh_from_db()
        self.assertEqual(
            self.trashed.name, 'Trashed Product',
            '★ 发布被拒了但 name 被改了 —— validate 里抛异常本应整体不落库',
        )

    # ── 3. 拒绝时不产生 UPDATE 审计（呼应 hard_delete 的幻影审计教训）──

    def test_rejected_publish_writes_no_update_audit(self):
        before = AuditLog.objects.filter(
            action=AuditLog.ACTION_UPDATE, object_id=str(self.trashed.pk)).count()

        self.client.patch(f'{URL}{self.trashed.pk}/', {'status': 'active'}, format='json')

        after = AuditLog.objects.filter(
            action=AuditLog.ACTION_UPDATE, object_id=str(self.trashed.pk)).count()
        self.assertEqual(after, before, '★ 被拒的发布留下了 UPDATE 审计（幻影审计）')

    # ── 4. 文案可操作：必须指向「回收站还原」这条出路 ──

    def test_conflict_message_points_to_recycle_bin_restore(self):
        resp = self.client.patch(
            f'{URL}{self.trashed.pk}/', {'status': 'active'}, format='json')
        body = resp.content.decode('utf-8', errors='ignore')

        self.assertIn('回收站', body, f'文案没给出路：{body[:400]}')
        self.assertIn('还原', body, f'文案没给出路：{body[:400]}')
        # 不得把端点路径/英文状态码甩给研究员
        self.assertNotIn('/api/', body)
        self.assertNotIn('relist', body)

    # ── 5. 正向出路：还原后照常发布（守卫不封路）──

    def test_restore_then_publish_works(self):
        restore = self.client.post(f'{URL}{self.trashed.pk}/restore/')
        self.assertEqual(restore.status_code, status.HTTP_200_OK, restore.content[:400])
        self.trashed.refresh_from_db()
        self.assertFalse(self.trashed.archived)

        resp = self.client.patch(
            f'{URL}{self.trashed.pk}/', {'status': 'active'}, format='json')
        self.assertEqual(
            resp.status_code, status.HTTP_200_OK,
            f'★ 还原之后仍然不能发布 —— 守卫把出路也堵死了：{resp.content[:400]}')

    # ── 6. 不误伤 ──

    def test_trashed_product_name_still_editable(self):
        resp = self.client.patch(
            f'{URL}{self.trashed.pk}/', {'name': 'Edited In Recycle Bin'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:400])
        self.trashed.refresh_from_db()
        self.assertEqual(self.trashed.name, 'Edited In Recycle Bin')

    def test_trashed_product_can_be_set_to_draft(self):
        """只有 `active` 会让它「看起来在售」；`draft` 是降级，不该拦。"""
        resp = self.client.patch(
            f'{URL}{self.trashed.pk}/', {'status': 'draft'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:400])
        self.trashed.refresh_from_db()
        self.assertEqual(self.trashed.status, Product.Status.DRAFT)

    def test_live_draft_product_publish_still_works(self):
        live = ProductFactory(name='Live Draft', slug='live-draft',
                              status=Product.Status.DRAFT, archived=False)
        resp = self.client.patch(
            f'{URL}{live.pk}/', {'status': 'active'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:400])
        live.refresh_from_db()
        self.assertEqual(live.status, Product.Status.ACTIVE)


class RecycleBinUnpublishStillWorksTest(TestCase):
    """回归：`POST archive/` → `PATCH status=active`（前端 `reactivateProduct`）必须仍然可用。

    这是「Unpublished」筛选下 Republish 按钮的真实路径 —— 该路径上 `archived` 布尔为
    **False**，所以不该被上面的守卫命中。锁住它，防止守卫写宽了把重新上架也堵死。
    """

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=UserFactory(is_staff=True))
        self.product = ProductFactory(name='Unpublished One', slug='unpublished-one',
                                      status=Product.Status.ACTIVE, archived=False)

    def test_archive_then_reactivate_roundtrip(self):
        r1 = self.client.post(f'{URL}{self.product.pk}/archive/')
        self.assertEqual(r1.status_code, status.HTTP_200_OK, r1.content[:400])
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ARCHIVED)
        self.assertFalse(self.product.archived)

        r2 = self.client.patch(
            f'{URL}{self.product.pk}/', {'status': 'active'}, format='json')
        self.assertEqual(
            r2.status_code, status.HTTP_200_OK,
            f'★ 重新上架（业务下架轴）被守卫误伤：{r2.content[:400]}')
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ACTIVE)
