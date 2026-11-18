"""A-043 契约测试：产品「读得到」必须「写得回」。

为什么需要它（真实代价）：
  `ProductDetailSerializer`（GET）与 `ProductCreateUpdateSerializer`（PUT）
  是两套手写字段清单，没有任何机制保证二者同步。历史上已经出现过
  「GET 返回了某字段，PUT 时被静默丢弃 / 直接 400」的情况 —— 前端照着自己
  读到的数据原样回写就丢字段，而这类丢失**不会报错**，只会让数据慢慢变空。

三层断言（广度与深度不可互替，缺一即盲区）：
  1. **静态层** —— 写序列化器的字段必须都能在详情序列化器里读到；
     例外必须进显式白名单，并写明「为什么只读」。
  2. **接口层** —— 真发一次 GET，键集必须覆盖全部写字段
     （防「Meta.fields 里有、但被 get_* 方法吃掉了」这类假一致）。
  3. **回环层** —— 把 GET 的响应原样 PUT 回去，必须 200，且逐字段值不变。
     这一层才抓得住「读出来的值写不回去」（枚举/格式/校验口径不一致）。

本文件自带一条元测试：白名单里每条都必须有理由，否则测试自己变红。
"""
import copy

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.api.v1.serializers import (
    ProductCreateUpdateSerializer,
    ProductDetailSerializer,
)
from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory

# ── 有意只读的字段：GET 会返回，但**不参与**回写。必须逐条给理由。 ──
INTENTIONALLY_READ_ONLY = {
    'id': '主键，回写无意义且会误导',
    'category_l1': '遗留 DB 列，新写入一律走 product_class_id（models.py:111 有明确注释）',
    'category_l2': '遗留 DB 列，同 category_l1：分类权威在 ProductClass 树，写入走 product_class_id',
    'product_class_name': '由 product_class 派生的展示名，非独立数据',
    'product_class_path': '由上卷分类派生的面包屑，非独立数据',
    'documents': '子资源，通过独立端点维护，不在产品本体回写',
    'method_links': '只读展示结构（含方法详情），写走 method_ids',
    'protocol_links': '只读展示结构（含协议详情），写走 protocol_ids',
    'reference_ids': '文献关联有独立端点',
    'compatibility_summary': '运行时聚合结果，不可写',
    'is_complete': '派生判定，不可写',
    'incomplete_items': '派生判定，不可写',
    'substructure_tags': '派生标签，不可写',
    'created_at': '系统时间戳',
    'updated_at': '系统时间戳',
}

# 写字段里「只写不读」的（提交后不会以同名字段回显）。每条都必须有真实理由。
INTENTIONALLY_WRITE_ONLY = {
    'research_goal_ids':
        '一次性级联入口：只用于把 goal 相关的 method 追加进链（纯追加、不删），'
        '产品与 ResearchGoal 之间没有存储关系，因此没有可回读的状态。'
        '（同理 application_ids 若将来只写不读，须在此登记）',
}


def _writable_fields():
    """写序列化器里真正可写的字段名集合。"""
    ser = ProductCreateUpdateSerializer()
    return {name for name, f in ser.fields.items() if not f.read_only}


class StaticContractTest(TestCase):
    """第 1 层：静态字段集"""

    def test_every_writable_field_is_readable(self):
        writable = _writable_fields()
        detail = set(ProductDetailSerializer().fields.keys())
        missing = writable - detail - set(INTENTIONALLY_WRITE_ONLY)
        self.assertEqual(
            missing, set(),
            f'这些字段能写但读不到（PUT 进去、GET 看不到）⇒ {sorted(missing)}',
        )

    def test_read_only_whitelist_entries_each_have_reason(self):
        for name, reason in INTENTIONALLY_READ_ONLY.items():
            self.assertTrue(reason and reason.strip(), f'{name} 没写只读理由')
            self.assertGreater(len(reason), 4, f'{name} 的理由太敷衍：{reason!r}')

    def test_no_stale_whitelist_entries(self):
        """白名单里不许留已经不存在的字段（防止白名单变成垃圾桶）。"""
        detail = set(ProductDetailSerializer().fields.keys())
        writable = _writable_fields()
        for name in INTENTIONALLY_READ_ONLY:
            self.assertTrue(
                name in detail or name in writable,
                f'白名单里的 {name} 两边都不存在了，应当删掉',
            )

    def test_no_unexplained_write_only_fields(self):
        writable = _writable_fields()
        detail = set(ProductDetailSerializer().fields.keys())
        write_only = writable - detail
        self.assertEqual(
            write_only, set(INTENTIONALLY_WRITE_ONLY),
            f'出现了没登记的「只写不读」字段 ⇒ {sorted(write_only)}',
        )
        for name, reason in INTENTIONALLY_WRITE_ONLY.items():
            self.assertGreater(len(reason or ''), 10, f'{name} 的只写理由太敷衍：{reason!r}')


class ApiContractTest(TestCase):
    """第 2/3 层：真实接口的键集与回环"""

    FIELDS = {
        'name': 'Contract Product',
        'slug': 'contract-product',
        'catalog_no': 'SC-CONTRACT-1',
        'cas': '1927-31-7',
        'smiles': 'CCO',
        'synonyms': ['ethanol', 'EtOH'],
        'inchi': 'InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3',
        'formula': 'C2H6O',
        'purity': '≥ 95% (HPLC)',
        'concentration': '100 mM',
        'storage': '-20°C',
        'shipping': 'Dry Ice',
        'lead_time': 'In stock, ships same day',
        'handling_notes': '避免反复冻融',
        'shelf_life': 'P2Y',
        'overview': '合同测试用产品',
        'usage': '仅供科研',
        'seo_title': 'Contract Product | SC',
        'seo_description': 'contract test',
        'status': 'draft',
    }

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=UserFactory(is_staff=True))
        self.product = ProductFactory(**self.FIELDS)

    def _get_detail(self, pk=None):
        pk = pk or self.product.pk
        resp = self.client.get(f'/api/v1/products/{pk}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json().get('data', resp.json())

    def test_get_detail_keys_cover_writable_fields(self):
        body = self._get_detail()
        writable = _writable_fields() - set(INTENTIONALLY_WRITE_ONLY)
        missing = writable - set(body.keys())
        self.assertEqual(
            missing, set(),
            f'GET 响应里缺少这些可写字段 ⇒ {sorted(missing)}',
        )

    def test_round_trip_put_with_own_response_preserves_fields(self):
        """GET 的响应原样 PUT 回去：必须 200，且每个字段值不变。"""
        before = self._get_detail()
        payload = {k: v for k, v in before.items()
                   if k not in INTENTIONALLY_READ_ONLY}
        payload = copy.deepcopy(payload)

        resp = self.client.put(f'/api/v1/products/{self.product.pk}/', payload, format='json')
        self.assertEqual(resp.status_code, 200,
                         f'原样回写被拒（读出来的值写不回去）：{resp.content[:500]}')

        after = self._get_detail()
        diffs = {
            k: (before.get(k), after.get(k))
            for k in before
            if k not in INTENTIONALLY_READ_ONLY
            and before.get(k) != after.get(k)
        }
        self.assertEqual(diffs, {}, f'回环后字段值变了：{diffs}')

    def test_empty_structure_svg_round_trips(self):
        """空结构式必须能回写。

        生产实测 141 条产品里 85 条（60%）`structure_svg` 为空。
        修复前详情序列化器把空值渲染成 JSON `null`，而 PUT 的 CharField
        `allow_null=False` ⇒ 「读出来原样写回去」直接 400。
        这条锁住「读得到的形状写得回去」。
        """
        product = ProductFactory(
            name='No Svg Product', slug='no-svg-product',
            catalog_no='SC-CONTRACT-3', structure_svg='',
        )
        before = self._get_detail(product.pk)
        self.assertEqual(before['structure_svg'], '',
                         '空结构式被渲染成了 null —— 回写必被 400 拦')

        payload = copy.deepcopy({
            k: v for k, v in before.items() if k not in INTENTIONALLY_READ_ONLY
        })
        resp = self.client.put(f'/api/v1/products/{product.pk}/', payload, format='json')
        self.assertEqual(resp.status_code, 200, f'空结构式写不回去：{resp.content[:400]}')

    def test_out_of_choices_value_is_rejected_not_silently_cleared(self):
        """枚举字段收到 choices 外的值时：**明确 400**，而不是静默清空。

        这是当前**有意保留**的口径，不是理想态：
          · 六个枚举字段（purity/concentration/storage/shipping/lead_time/shelf_life）
            的 choices 里都用 `CUSTOM = ''` 表示「自定义输入」，
            所以任意自由文本在写入侧不合法。
          · 生产实测 141 条产品这六个字段**全部 0 条越界**（2026-11-18），
            因此目前没有真实数据踩到；一旦有人写入自定义文本，
            表现是「400 报错」而不是「悄悄把值抹成空串」——后者才是数据悬崖。
          · 如果将来确实需要自由文本，正确做法是改模型（加 _custom 列或去掉 choices）
            + 迁移，而不是在这里放宽校验。
        """
        product = ProductFactory(
            name='Custom Purity Product', slug='custom-purity-product',
            catalog_no='SC-CONTRACT-2', purity='≥ 95%（实验室自制）',
        )
        before = self._get_detail(product.pk)
        self.assertEqual(before['purity'], '≥ 95%（实验室自制）')

        payload = copy.deepcopy({
            k: v for k, v in before.items() if k not in INTENTIONALLY_READ_ONLY
        })
        resp = self.client.put(f'/api/v1/products/{product.pk}/', payload, format='json')
        self.assertEqual(resp.status_code, 400,
                         'choices 外取值被接受了 —— 说明校验口径变了，本用例需重判')
        self.assertIn('purity', str(resp.json()))

        product.refresh_from_db()
        self.assertEqual(product.purity, '≥ 95%（实验室自制）',
                         '被拒绝时不该改动库里的值（不许半写）')
