"""RFQ 明细必须保存「客户手填的名称/货号」（A-026，2026-11-27）。

## 改前是什么样（实测）
客户端 RFQ 表单允许只填产品名、不挂产品（`product_id` 可为 null），但提交时
前端 `.map()` 只送 `product_id / quantity / note` —— **手填的名称与货号被丢掉**，
`sku` 更是从来没送过。于是后端落一条 `product=NULL, sku=NULL, note=''` 的明细：
运营在 RFQ Inbox 看到 **PRODUCT "—" / SKU "—"**，无从判断客户要什么。

dev 实测：`quote_request_item` 91 行里 **91 行** product 与 sku 同时为 NULL。

## 本文件钉三条
① 手填名称/货号能落库；
② 详情接口把它们返回（否则前端仍然显示 "—"）；
③ 不填时是空串而不是 NULL（避免前端要处理两种"没有"）。
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.quotes.models import QuoteRequestItem


@pytest.mark.django_db
class TestRfqItemRequestedText:
    def _submit(self, items):
        c = APIClient()
        return c.post('/api/v1/quote-requests/', {
            'contact_name': 'Wei Zhang',
            'contact_email': 'wei@example.edu',
            'items': items,
        }, format='json')

    def test_free_text_item_is_persisted(self):
        r = self._submit([{
            'requested_product_name': 'Pseudo-UTP 100 mM',
            'requested_catalog_no': 'SC8023-1',
            'quantity': 10,
            'note': '10 µL',
        }])
        assert r.status_code == 201, r.content[:400]
        item = QuoteRequestItem.objects.latest('id')
        assert item.requested_product_name == 'Pseudo-UTP 100 mM'
        assert item.requested_catalog_no == 'SC8023-1'
        assert item.product_id is None and item.sku_id is None

    def test_detail_returns_the_text_fields(self):
        r = self._submit([{
            'requested_product_name': 'Pseudo-UTP 100 mM',
            'requested_catalog_no': 'SC8023-1',
        }])
        qid = r.json()['data']['id']
        # 详情端点仅 staff 可读（RFQ Inbox 是运营台）⇒ 必须带身份
        staff = APIClient()
        staff.force_authenticate(UserFactory(is_staff=True))
        resp = staff.get(f'/api/v1/quote-requests/{qid}/')
        assert resp.status_code == 200, resp.content[:300]
        d = resp.json()['data']
        assert d['items'][0]['requested_product_name'] == 'Pseudo-UTP 100 mM'
        assert d['items'][0]['requested_catalog_no'] == 'SC8023-1'

    def test_omitted_text_defaults_to_empty_string(self):
        r = self._submit([{'quantity': 1}])
        assert r.status_code == 201, r.content[:400]
        item = QuoteRequestItem.objects.latest('id')
        assert item.requested_product_name == ''
        assert item.requested_catalog_no == ''
