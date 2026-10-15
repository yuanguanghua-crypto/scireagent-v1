"""★ QuoteViewSet 只读化回归（2026-10-15）。

背景：`QuoteViewSet`（apps/transactions）此前 create 落到 `QuoteListSerializer`
（列表用的序列化器，fields 只有 id/quote_no/company_name/contact_name/status/grand_total/created_at，
**不含 items、不含联系字段**）⇒ **已登录** `POST /api/v1/quotes/` 会建出**空壳询价单**
（`quote_no=null`、`grand_total=0.00`、无 items）。

客户侧真实询价入口是 **`/quote-requests/`**（apps/quotes，另一个 app）；前端对 `/quotes/` **只做 GET**
（`frontend/src/api/poPortal.js:15`）。

修法：`http_method_names = ['get', 'head', 'options']` —— 写方法一律 405。

★ 注意 DRF 语义（易错）：`dispatch()` **先** `check_permissions()` **再**查方法
⇒ 匿名写仍应 **401**（权限先拦），只有"**过了鉴权但方法被禁**"才是 **405**。两条都要锁住。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.transactions.models import Quote


class QuoteReadOnlyTest(TestCase):
    """已登录也不能 POST /quotes/（防建空壳单）；匿名仍 401；匿名读仍 200。"""

    def test_anon_post_quotes_is_401(self):
        """权限先于方法：匿名 POST 仍是 401（不是 405），且不落库。"""
        r = APIClient().post('/api/v1/quotes/', {'quote_no': 'QT-RO-ANON'}, format='json')
        self.assertEqual(r.status_code, 401, r.content[:300])
        self.assertFalse(Quote.objects.filter(quote_no='QT-RO-ANON').exists())

    def test_authed_post_quotes_is_405(self):
        """已登录用户 POST /quotes/ 必须 405。

        此前会建出 `quote_no=null`/`grand_total=0.00`/无 items 的空壳单（实测 id=2 即此形态）。
        """
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        r = client.post('/api/v1/quotes/', {'quote_no': 'QT-RO-AUTH'}, format='json')
        self.assertEqual(r.status_code, 405, r.content[:300])
        self.assertFalse(Quote.objects.filter(quote_no='QT-RO-AUTH').exists())

    def test_anon_get_quotes_is_200(self):
        """公开读契约不得被误伤：匿名 GET 仍 200（空列表）。"""
        r = APIClient().get('/api/v1/quotes/')
        self.assertEqual(r.status_code, 200, r.content[:300])
