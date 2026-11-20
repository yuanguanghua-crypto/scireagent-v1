"""`?status__in=` 服务端多状态筛选（S5 P-2）。

## 为什么需要
两个运营台原先 `getOrders({page_size: 200})` 拉一页、再在客户端按状态筛。
`status` 是精确匹配 ⇒ 一次只能筛一个状态 ⇒ 只能整页拉回自己筛 ⇒
累计单量越过 200 后，被挤出那一页的订单**静默消失**（本地实测 confirmed 漏 70/94）。
本文件钉住两件事：
  ① `status__in` 真的按集合筛，且**翻页能覆盖整个队列**（不再有 200 单天花板）；
  ② 原有 `?status=` 精确筛的契约没被这次改造改坏。
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.transactions.models import Order

User = get_user_model()
URL = '/api/v1/orders/'


class OrderStatusInFilterTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='FilterOrg', org_type='academic')
        self.proc = User.objects.create_user(
            username='filter_proc', email='filter_proc@example.com', password='x',
            role='procurement', organization=self.org,
        )

        def mk(no, status):
            return Order.objects.create(
                user=self.proc, organization=self.org,
                order_no=no, po_number=None, status=status,
            )

        self.c1 = mk('ORD-FLT-C1', Order.Status.CONFIRMED)
        self.c2 = mk('ORD-FLT-C2', Order.Status.CONFIRMED)
        self.s1 = mk('ORD-FLT-S1', Order.Status.SHIPPED)
        self.d1 = mk('ORD-FLT-D1', Order.Status.DELIVERED)
        self.dr1 = mk('ORD-FLT-DR1', Order.Status.DRAFT)

    def _get(self, query=''):
        c = APIClient()
        c.force_authenticate(self.proc)
        r = c.get(URL + query)
        body = r.json() if r.content else {}
        return r.status_code, body

    def _ids(self, query=''):
        code, body = self._get(query)
        self.assertEqual(code, 200, body)
        data = body.get('data') or {}
        results = data.get('results') if isinstance(data, dict) else data
        return {o['id'] for o in (results or [])}

    def _page(self, query=''):
        """返回 (总数, id 集合, next)。总数兼容两种信封（P2-1 已知的分页 meta 三套写法）。"""
        code, body = self._get(query)
        self.assertEqual(code, 200, body)
        data = body.get('data')
        pag = (body.get('meta') or {}).get('pagination') or {}
        if isinstance(data, dict):
            pag = pag or data
            results = data.get('results') or []
        else:
            results = data or []
        return pag.get('count'), {o['id'] for o in results}, pag.get('next')

    # ── ① 多状态一次筛 ─────────────────────────────────
    def test_status_in_filters_by_set(self):
        """`status__in=confirmed,shipped` 只返回这两类。"""
        ids = self._ids('?status__in=confirmed,shipped')
        self.assertEqual(ids, {self.c1.id, self.c2.id, self.s1.id},
                         '多状态筛应当只返回 confirmed + shipped')

    def test_status_in_single_value(self):
        ids = self._ids('?status__in=delivered')
        self.assertEqual(ids, {self.d1.id})

    # ── ② 老契约不能被改坏 ────────────────────────────
    def test_exact_status_still_works(self):
        """`?status=confirmed` 精确筛保持原行为（改造前的主用法）。"""
        ids = self._ids('?status=confirmed')
        self.assertEqual(ids, {self.c1.id, self.c2.id})

    def test_exact_status_invalid_is_400(self):
        """精确筛的非法值仍是 400（与改造前一致，不静默空表）。"""
        code, _ = self._get('?status=nonexistent')
        self.assertEqual(code, 400)

    # ── ③ 多状态筛的非法值也必须 400 ──────────────────
    def test_status_in_typo_is_rejected(self):
        """拼错的状态值必须 400 —— 静默空表会被误读成"队列里没单了"。"""
        code, _ = self._get('?status__in=confimed')
        self.assertEqual(code, 400, '拼错的状态值不应静默返回空列表')

    # ── ④ ★ 关键：翻页能覆盖整个队列（原来 200 单天花板）──
    def test_pagination_covers_whole_queue(self):
        """造 30 张 confirmed，按 page_size=10 翻完 ⇒ 30 张全拿到，count 也是 30。

        这条正对着原缺陷：旧实现只取一页（200），越界的订单运营永远看不到。
        """
        extra = []
        for i in range(28):  # 已有 2 张，凑 30
            extra.append(Order.objects.create(
                user=self.proc, organization=self.org,
                order_no=f'ORD-FLT-BULK-{i:03d}', po_number=None,
                status=Order.Status.CONFIRMED,
            ))
        expected = {self.c1.id, self.c2.id} | {o.id for o in extra}
        self.assertEqual(len(expected), 30)

        seen = set()
        counts = []
        nexts = []
        for page in (1, 2, 3):
            count, ids, nxt = self._page(f'?status__in=confirmed&page_size=10&page={page}')
            counts.append(count)
            nexts.append(bool(nxt))
            seen |= ids

        self.assertEqual(counts, [30, 30, 30], 'count 应恒为队列总数（不是当前页条数）')
        self.assertEqual(nexts, [True, True, False], '前两页应有下一页、第三页应到底')
        self.assertEqual(seen, expected, '翻完三页必须恰好覆盖全部 30 张 confirmed')

    def test_invoicing_queue_statuses_are_reachable(self):
        """开票台的两个状态（delivered / invoiced）一次筛得出来。"""
        inv = Order.objects.create(
            user=self.proc, organization=self.org,
            order_no='ORD-FLT-INV1', po_number=None, status=Order.Status.INVOICED,
        )
        ids = self._ids('?status__in=delivered,invoiced')
        self.assertEqual(ids, {self.d1.id, inv.id})
