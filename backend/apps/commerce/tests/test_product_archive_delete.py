"""产品下架（archive）与删除（destroy）测试。

- archive @action：staff 下架产品，status -> archived，前台不可见，可恢复。
- destroy：物理删除，SKU 级联删除。
- 前台过滤：非 staff 请求只看 active，下架/草稿不进列表且无法用 status 参数绕过。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import Product, SKU
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class ProductArchiveTest(TestCase):
    """下架动作"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.product = ProductFactory(name='Archive Me', status='active')

    def test_staff_can_archive_product(self):
        """staff POST archive -> 200，status 变 archived"""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/archive/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ARCHIVED)

    def test_anonymous_cannot_archive(self):
        """匿名下架 -> 401/403，status 不变"""
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/archive/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ACTIVE)

    def test_non_staff_cannot_archive(self):
        """非 staff 下架 -> 403"""
        self.client.force_authenticate(user=UserFactory(is_staff=False))
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/archive/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class ProductDestroyTest(TestCase):
    """删除动作（Plan B：默认软归档，不物理删除）"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.product = ProductFactory(name='Delete Me', status='active')

    def test_staff_delete_soft_archives(self):
        """staff DELETE -> 200，产品软归档（仍在 DB，archived=True）"""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.product.refresh_from_db()
        self.assertTrue(self.product.archived)

    def test_soft_delete_keeps_skus(self):
        """软删不级联物理删 SKU（行为变更：不再 CASCADE 硬删）"""
        sku = SKUFactory(product=self.product, sku_code='KEPT-SKU')
        self.client.force_authenticate(user=self.staff)
        self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertTrue(SKU.objects.filter(pk=sku.pk).exists())

    def test_anonymous_cannot_delete(self):
        """匿名删除 -> 401/403"""
        resp = self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_non_staff_cannot_delete(self):
        """非 staff 删除 -> 403"""
        self.client.force_authenticate(user=UserFactory(is_staff=False))
        resp = self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class ProductNumberUniquenessContractTest(TestCase):
    """唯一性口径：货号 / slug 均为「全表永久唯一」（回收站行照常占位）。

    语义依据：**货号是产品的永久身份**（印在瓶签 / COA / SDS / 订单 / 文献引用上）。
    归档（archived=True）**不释放编号**——否则同一货号会指向另一个分子，
    客户拿到的 SC8001 与它的 COA 对不上，真实网站绝不允许这种情况。

    本类取代旧的「删后重导静默复活」契约（旧行为：命中 archived 行则 un-archive 并用
    新数据覆盖 —— 无 CREATE 审计、旧数据被静默改写）。新契约：

    - 命中**回收站行** → **409** + 可操作提示（走 restore / 换编号 / hard-delete 重来）
    - 命中**在售行**   → **400**（真重复）
    - 更新自身**未改动**编号 → 不误报
    - 归档行**绝不**被静默覆盖（不复活、不改名、不动其 SKU）
    """

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)

    def _post_create(self, payload):
        self.client.force_authenticate(user=self.staff)
        return self.client.post('/api/v1/products/', payload, format='json')

    # ── ① 回收站行占位 → 409（且不被静默覆盖）─────────────────────────
    def test_create_with_archived_catalog_no_conflicts_409(self):
        """catalog_no 命中回收站行 → 409；该行原封不动（仍归档、名字没被覆盖）。"""
        p = ProductFactory(catalog_no='SC-RESTORE-1', name='Old Name', status='active')
        p.archived = True
        p.save()
        resp = self._post_create({
            'name': 'New Restored', 'catalog_no': 'SC-RESTORE-1',
            'slug': 'brand-new-slug-1', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        p.refresh_from_db()
        self.assertTrue(p.archived, '归档行不得被静默复活')
        self.assertEqual(p.name, 'Old Name', '归档行数据不得被静默覆盖')
        self.assertEqual(
            Product.objects.filter(catalog_no='SC-RESTORE-1').count(), 1,
            '不得新建出第二条同货号记录')

    def test_conflict_message_is_actionable(self):
        """409 的消息必须可操作（含 restore 出路），否则研究员无从下手。"""
        p = ProductFactory(catalog_no='SC-RESTORE-HINT', status='active')
        p.archived = True
        p.save()
        resp = self._post_create({
            'name': 'X', 'catalog_no': 'SC-RESTORE-HINT',
            'slug': 'new-slug-hint', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        msg = resp.json()['meta']['error']['message']
        self.assertIn('回收站', msg)
        self.assertIn('restore', msg)

    def test_create_with_archived_slug_conflicts_409(self):
        """★真实场景（本研究项目的实际卡点）：前端 ensureSlug() = slugify(catalog_no)。

        重导老货号时，即使把 catalog_no 改成一个新值，slug 仍会与回收站行相同
        —— 必须 409（而不是不可操作的 400）。
        """
        p = ProductFactory(catalog_no='SC-SLUG-1', slug='sc-slug-1', status='active')
        p.archived = True
        p.save()
        resp = self._post_create({
            'name': 'X', 'catalog_no': 'SC-SLUG-1-NEW', 'slug': 'sc-slug-1', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        p.refresh_from_db()
        self.assertTrue(p.archived)

    def test_archived_row_keeps_its_skus(self):
        """契约变更后：归档行的 SKU 绝不能因"重导"被顺手改掉/删掉。"""
        p = ProductFactory(catalog_no='SC-RESTORE-2', status='active')
        sku = SKUFactory(product=p, sku_code='KEEP-ME')
        p.archived = True
        p.save()
        resp = self._post_create({
            'name': 'Restored', 'catalog_no': 'SC-RESTORE-2',
            'slug': 'new-sc-restore-2', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(SKU.objects.filter(pk=sku.pk).exists())
        p.refresh_from_db()
        self.assertTrue(p.archived)

    # ── ② 在售行占位 → 400（真重复）────────────────────────────────
    def test_create_with_active_duplicate_catalog_no_still_400(self):
        ProductFactory(catalog_no='SC-DUP-1', name='Existing', status='active')
        resp = self._post_create({
            'name': 'Clash', 'catalog_no': 'SC-DUP-1', 'slug': 'new-sc-dup-1', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_with_active_duplicate_slug_still_400(self):
        ProductFactory(catalog_no='SC-DUP-9', slug='taken-slug', status='active')
        resp = self._post_create({
            'name': 'Clash', 'catalog_no': 'SC-DUP-9-NEW', 'slug': 'taken-slug', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── ③ 干净创建仍通；必填语义不回退 ────────────────────────────────
    def test_create_fresh_number_succeeds(self):
        resp = self._post_create({
            'name': 'Fresh', 'catalog_no': 'SC-FRESH-1', 'slug': 'sc-fresh-1', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_create_requires_slug(self):
        """slug 改为显式声明（validators=[]）后，required 语义不得回退：无 slug → 400。"""
        resp = self._post_create({'name': 'No Slug', 'catalog_no': 'SC-NOSLUG-1', 'status': 'draft'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── ④ 更新路径：自身编号不误报；改成被占用的编号要挡住 ──────────────
    def test_update_keeping_own_numbers_is_ok(self):
        p = ProductFactory(catalog_no='SC-UPD-1', slug='sc-upd-1', status='draft')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(f'/api/v1/products/{p.pk}/', {'name': 'Renamed'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_to_archived_catalog_no_conflicts_409(self):
        archived = ProductFactory(catalog_no='SC-UPD-TAKEN', status='active')
        archived.archived = True
        archived.save()
        p = ProductFactory(catalog_no='SC-UPD-2', slug='sc-upd-2', status='draft')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(
            f'/api/v1/products/{p.pk}/', {'catalog_no': 'SC-UPD-TAKEN'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        p.refresh_from_db()
        self.assertEqual(p.catalog_no, 'SC-UPD-2', '冲突时不得写入')


class ProductPublicStatusFilterTest(TestCase):
    """前台列表状态过滤隐患修复"""

    def setUp(self):
        self.client = APIClient()
        # 公开列表只应看到 active 这一条
        ProductFactory(name='Active', status='active')
        ProductFactory(name='Draft', status='draft')
        ProductFactory(name='Archived', status='archived')
        ProductFactory(name='Deprecated', status='deprecated')

    def test_anonymous_list_only_active(self):
        """匿名列表只返回 active 产品"""
        resp = self.client.get('/api/v1/products/')
        names = [p['name'] for p in resp.json()['data']]
        self.assertEqual(names, ['Active'])

    def test_anonymous_cannot_bypass_with_status_param(self):
        """匿名 ?status=draft 也无法绕过，仍只返回 active"""
        resp = self.client.get('/api/v1/products/?status=draft')
        names = [p['name'] for p in resp.json()['data']]
        self.assertEqual(names, ['Active'])

    def test_staff_sees_all_statuses(self):
        """staff 不受过滤，可见全部状态"""
        self.client.force_authenticate(user=UserFactory(is_staff=True))
        resp = self.client.get('/api/v1/products/')
        names = {p['name'] for p in resp.json()['data']}
        self.assertEqual(names, {'Active', 'Draft', 'Archived', 'Deprecated'})
