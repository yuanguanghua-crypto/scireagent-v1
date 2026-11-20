"""`?has_documents=` 服务端筛选（S5 P-2 收尾）。

## 为什么需要
下载中心（`PoDownloadCenter.vue`）此前的取数是
`fetchOrders({ page_size: 100 })`，再在客户端用 `o.invoice || o.attachments.length` 过滤。
本地只读实测（全库 1124 单）：**有发票的共 267 单**，其中只有一小部分落在最新的 100 单里
⇒ 客户更早的发票 / PO 附件**在下载中心根本不出现**，页面还显示
"No downloadable documents yet"（看起来像"确实没有文档"）。

本文件钉住四件事：
  ① `has_documents=1` 精确等于「有发票 **或** 有附件」，不多不少；
  ② 一个订单挂 2 个附件时**不得重复出现**（反向 FK 的 JOIN 去重）；
  ③ 不传该参数时全量返回 —— 既有列表契约不变；
  ④ 它**只是显示层筛选**，不会绕过 `get_queryset()` 的可见范围（客户仍只看自己的单）。
"""
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.transactions.models import Invoice, Order, PoAttachment

User = get_user_model()
URL = '/api/v1/orders/'


class OrderHasDocumentsFilterTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.org = Organization.objects.create(name='DocFilterOrg', org_type='academic')
        self.proc = User.objects.create_user(
            username='docfilter_proc', email='docfilter_proc@example.com', password='x',
            role='procurement', organization=self.org,
        )

        def mk(no, status=Order.Status.INVOICED):
            return Order.objects.create(
                user=self.proc, organization=self.org,
                order_no=no, po_number=None, status=status,
            )

        # ① 只有发票
        self.with_invoice = mk('ORD-DOC-INV')
        Invoice.objects.create(
            order=self.with_invoice, invoice_no='INV-DOC-1', due_date=date(2026, 12, 31),
        )
        # ② 只有 1 个附件
        self.with_att = mk('ORD-DOC-ATT', Order.Status.DELIVERED)
        # ③ 有 2 个附件（用于验证 distinct：不得出现两行）
        self.two_att = mk('ORD-DOC-ATT2', Order.Status.DELIVERED)
        # ④ 什么都没有
        self.bare = mk('ORD-DOC-NONE', Order.Status.CONFIRMED)

        with override_settings(MEDIA_ROOT=self.tmp):
            for order in (self.with_att, self.two_att):
                count = 1 if order is self.with_att else 2
                for i in range(count):
                    PoAttachment.objects.create(
                        order=order,
                        file=SimpleUploadedFile(
                            f'po-{order.id}-{i}.txt', b'att',
                            content_type='text/plain',
                        ),
                        original_filename=f'po-{order.id}-{i}.txt',
                        mime_type='text/plain', file_size=3,
                        uploaded_by=self.proc,
                    )

    def _get(self, query=''):
        c = APIClient()
        c.force_authenticate(self.proc)
        r = c.get(URL + query)
        body = r.json() if r.content else {}
        return r.status_code, body

    def _page(self, query=''):
        """返回 (count, id 列表)。兼容两种信封（`meta.pagination` 与 `data.results`）。"""
        code, body = self._get(query)
        self.assertEqual(code, 200, body)
        data = body.get('data')
        pag = (body.get('meta') or {}).get('pagination') or {}
        if isinstance(data, dict):
            results = data.get('results') or []
        else:
            results = data or []
        return pag.get('count'), [o['id'] for o in results]

    # ── ① 精确等于「有发票 或 有附件」──────────────────
    def test_has_documents_returns_orders_with_invoice_or_attachment(self):
        _, ids = self._page('?has_documents=1&page_size=100')
        self.assertEqual(set(ids), {self.with_invoice.id, self.with_att.id, self.two_att.id})
        self.assertNotIn(self.bare.id, ids, '没有文档的订单不应出现在下载数据里')

    def test_without_documents_returns_only_bare_orders(self):
        _, ids = self._page('?has_documents=0&page_size=100')
        self.assertEqual(set(ids), {self.bare.id})

    # ── ② 多附件不得重复 ─────────────────────────────
    def test_multi_attachment_order_is_not_duplicated(self):
        """挂 2 个附件的订单只能出现一次（反向 FK JOIN 后必须 distinct）。"""
        count, ids = self._page('?has_documents=1&page_size=100')
        self.assertEqual(ids.count(self.two_att.id), 1, '多附件订单在结果里重复出现')
        self.assertEqual(len(ids), 3)
        self.assertEqual(count, 3, 'count 也必须是去重后的 3（否则前端计数字段会骗人）')

    # ── ③ 不传参数 ⇒ 全量（既有契约不变）──────────────
    def test_no_param_returns_everything(self):
        _, ids = self._page('?page_size=100')
        self.assertEqual(len(ids), 4, '不传 has_documents 时必须返回全部订单')

    def test_no_param_includes_bare_orders(self):
        _, ids = self._page('?page_size=100')
        self.assertIn(self.bare.id, ids)

    # ── ④ 非法值 400，不静默降级 ─────────────────────
    def test_invalid_value_is_400(self):
        code, _ = self._get('?has_documents=abc')
        self.assertEqual(code, 400, '非法值不能静默当成"没筛"（会把没文档的也列出来）')

    # ── 组合过滤 ────────────────────────────────────
    def test_combines_with_status_in(self):
        _, ids = self._page('?has_documents=1&status__in=delivered&page_size=100')
        self.assertEqual(set(ids), {self.with_att.id, self.two_att.id})

    def test_combines_with_organization_id(self):
        _, ids = self._page(f'?has_documents=1&organization_id={self.org.id}&page_size=100')
        self.assertEqual(len(ids), 3)

    # ── ⑤ 不得放大可见范围（客户仍只看自己的单）────────
    def test_does_not_widen_visibility_for_customers(self):
        """另造一个客户的已开票订单：客户用 has_documents=1 也只能看到自己的。"""
        other = User.objects.create_user(
            username='docfilter_cust', email='docfilter_cust@example.com', password='x',
            role='researcher', organization=self.org,
        )
        foreign = Order.objects.create(
            user=other, organization=self.org,
            order_no='ORD-DOC-FOREIGN', po_number=None, status=Order.Status.INVOICED,
        )
        Invoice.objects.create(
            order=foreign, invoice_no='INV-DOC-2', due_date=date(2026, 12, 31),
        )
        mine = Order.objects.create(
            user=self.proc, organization=self.org,
            order_no='ORD-DOC-MINE', po_number=None, status=Order.Status.INVOICED,
        )
        Invoice.objects.create(
            order=mine, invoice_no='INV-DOC-3', due_date=date(2026, 12, 31),
        )

        c = APIClient()
        c.force_authenticate(other)
        r = c.get(URL + '?has_documents=1&page_size=100')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        data = body.get('data')
        results = data.get('results') if isinstance(data, dict) else (data or [])
        ids = {o['id'] for o in results}
        self.assertIn(foreign.id, ids)
        self.assertNotIn(mine.id, ids, 'has_documents 不能成为跨客户查看别人订单的通道')
        self.assertNotIn(self.with_invoice.id, ids)
