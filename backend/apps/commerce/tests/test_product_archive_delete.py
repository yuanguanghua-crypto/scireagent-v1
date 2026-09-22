"""产品下架（archive）与删除（destroy）测试。

- archive @action：staff 下架产品，status -> archived，前台不可见，可恢复。
- destroy：物理删除，SKU 级联删除。
- 前台过滤：非 staff 请求只看 active，下架/草稿不进列表且无法用 status 参数绕过。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import Product, SKU, AuditLog
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.bridges.models import ProductReagentClass
from apps.knowledge.models import ReagentClass


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

    # ── ⑤ 409 文案承诺的三条「出路」必须真的可用（S5.1）────────────
    def test_restore_path_from_409_advice_works(self):
        """出路①：按 409 提示调 restore → 归档行复活，编号仍归它。"""
        p = ProductFactory(catalog_no='SC-ADV-1', slug='sc-adv-1', status='active')
        p.archived = True
        p.save()
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(f'/api/v1/products/{p.pk}/restore/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        p.refresh_from_db()
        self.assertFalse(p.archived)

    def test_hard_delete_path_from_409_advice_works(self):
        """出路③：先 hard-delete（仅超管）→ 编号被释放 → 同货号可重新 create。

        这条必须是绿的：它是 409 文案对研究员作出的承诺。
        """
        superuser = UserFactory(is_staff=True, is_superuser=True)
        p = ProductFactory(catalog_no='SC-ADV-2', slug='sc-adv-2', status='active')
        p.archived = True
        p.save()
        self.client.force_authenticate(user=superuser)
        resp = self.client.post(f'/api/v1/products/{p.pk}/hard-delete/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp2 = self._post_create({
            'name': 'Reborn', 'catalog_no': 'SC-ADV-2', 'slug': 'sc-adv-2', 'status': 'draft'})
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED,
                         'hard-delete 后编号应被释放（409 文案承诺的出路③）')


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


class ProductHardDeleteProtectedTest(TestCase):
    """hard-delete 的两个缺陷（批甲 **B1 / B2**，2026-09-22 修复）。

    - **B1**：被 `PROTECT` 关联挡住时，原先**未捕获 `ProtectedError`** ⇒ 返回 **500**
      （DEBUG 下还吐堆栈页），且 B′ 的 409 文案恰让用户"先 hard-delete 旧记录" ⇒ **走进死路**。
      现在应为 **409** + 可操作文案。
    - **B2**：原先"**先写审计、再 `delete()`**" ⇒ 删除失败时那条 `HARD_DELETE` 审计**已落库**
      ⇒ 审计谎称"已物理删除"而产品仍在（**幻影审计**，生产/dev 实测 4 例）。
      现在两步同处一个 `transaction.atomic()` ⇒ 删除失败即**整体回滚**，审计不残留。

    挡路的关联来源：`ProductReagentClass.product`
    （`apps/bridges/models.py:420`，`on_delete=PROTECT`）。
    """

    def setUp(self):
        self.client = APIClient()
        self.superuser = UserFactory(is_staff=True, is_superuser=True)

    def _hard_delete(self, pid):
        self.client.force_authenticate(user=self.superuser)
        return self.client.post(f'/api/v1/products/{pid}/hard-delete/')

    def _attach_reagent_class(self, product):
        rc = ReagentClass.objects.create(
            id_code='RC-HD-TEST', name='Hard-delete Test RC', slug='rc-hd-test',
        )
        return ProductReagentClass.objects.create(product=product, reagent_class=rc)

    # ── B1：应为 409（而不是 500）────────────────────────────
    def test_hard_delete_blocked_by_protected_fk_returns_409(self):
        p = ProductFactory()
        self._attach_reagent_class(p)
        resp = self._hard_delete(p.id)
        self.assertEqual(
            resp.status_code, status.HTTP_409_CONFLICT,
            '被 PROTECT 关联挡住应返回 409，而不是 500（B1）',
        )
        # ⚠️ 本项目信封的 `meta.error.code` 是**按 HTTP 状态码派生**的
        #   （`core/exceptions.py:26-36`，409 → 'conflict'），**完全不读 `default_code`**
        #   ⇒ 这里只能断言 'conflict'；语义细节由 status + message 承载
        #   （与 B′ 的 C2b/C2c 同口径；其判据行本就写 code=conflict）。
        self.assertEqual(resp.json()['meta']['error']['code'], 'conflict')

    def test_409_message_is_actionable(self):
        """文案必须给得出路，否则研究员无从下手（与 B′ 的 409 体例一致）。"""
        p = ProductFactory()
        self._attach_reagent_class(p)
        msg = self._hard_delete(p.id).json()['meta']['error']['message']
        self.assertIn('软归档', msg)
        self.assertIn('ProductReagentClass', msg)

    def test_hard_delete_without_dependents_still_200(self):
        """反例：无 PROTECT 关联时，硬删必须**照常 200**（别把正常路径改坏）。"""
        p = ProductFactory()
        resp = self._hard_delete(p.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Product.objects.filter(id=p.id).exists())

    # ── B2：失败后不得留下幻影审计，且产品仍须存在 ─────────────
    def test_blocked_hard_delete_leaves_no_phantom_audit(self):
        p = ProductFactory()
        self._attach_reagent_class(p)
        self._hard_delete(p.id)
        self.assertTrue(
            Product.objects.filter(id=p.id).exists(),
            '删除失败 ⇒ 产品必须仍在（不得半删）',
        )
        self.assertEqual(
            AuditLog.objects.filter(
                action=AuditLog.ACTION_HARD_DELETE, object_id=p.id,
            ).count(),
            0,
            'B2 幻影审计：删除失败时不得留下 HARD_DELETE 审计（事务必须整体回滚）',
        )
