# -*- coding: utf-8 -*-
"""注册面收紧 —— role 不可自助提权 + join 机构需邮箱域名匹配（2026-10-21 L7）

## 为什么要有这两条
`procurement` 这个角色在本仓库里是**供应商内部运营**身份：`core/permissions.py:44-51`
的 `IsProcurementOrAdmin` 保护了 13 个端点，逐条看全是内部动作 ——
审批订单、拒绝、取消、指派销售、备货锁库存、新建发货、标记发货/送达、开票、
收款（`services.py:519` 写死 `status=VERIFIED`）、AR 账龄、改库存、机构管理。
客户的采购经理**一项都用不上**。

而注册端点曾是 `AllowAny` 且 `role` 是客户端可选的
（旧代码 `ROLE_CHOICES = (('researcher',...), ('procurement',...))`，
`validate()` 只挡了 `editor`/`admin`）⇒ **任何人注册时勾一下就拿全部内部权限**，
成本只是一个自己的邮箱。

第二条同理：`organization_choice='join'` 曾是"有 org id 就进"，
org id 还能从匿名端点 `GET /api/v1/organizations` 拿到 ⇒ 成为"同机构成员"后
`_is_order_viewer`（`po_views.py:319-320`）就放行该机构**全部**发票 PDF /
PO 附件 / 代客户接受报价。机构身份必须有个不可自助伪造的凭据 ——
最轻的一个就是**机构邮箱域名**（机构自己控制 DNS，攻击者伪造不了）。

## 判据（本文件钉住的契约）
1. 注册永远落 `role='researcher'`，无论客户端传什么（只保留 `editor`/`admin` 的 400）
2. `join` 要求：机构 `contact_email` 非空 且 域名不是公共邮箱 且 注册邮箱域名相同
3. 域名比较大小写不敏感

## ⚠️ 已核实：注册响应里不含 `role`
`RegisterView.post()`（`views.py:36-49`）只回 `detail`/`email`/`email_verified`
⇒ 前端拿不到 role，落库固定不影响任何前端逻辑。
"""
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, User
from apps.accounts.tests.factories import UserFactory

REGISTER_URL = '/api/v1/auth/register'


def _payload(**over):
    data = {
        'username': 'newuser',
        'email': 'new@bcm.edu',
        'password': 'testpass123',
        'password_confirm': 'testpass123',
        'role': 'researcher',
        'organization_choice': 'solo',
    }
    data.update(over)
    return data


class RegistrationRoleGuardTests(APITestCase):
    """role 不得由注册者自选 —— 尤其是 procurement。"""

    def test_procurement_choice_downgraded_to_researcher(self):
        """核心用例：勾了 Procurement Manager 也只拿到 researcher。"""
        resp = self.client.post(
            REGISTER_URL, _payload(username='pm1', email='pm1@bcm.edu', role='procurement'),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        user = User.objects.get(username='pm1')
        self.assertEqual(
            user.role, User.Role.RESEARCHER,
            '注册者自选 procurement 拿到了内部运营身份 ⇒ 提权漏洞')

    def test_researcher_choice_stays_researcher(self):
        resp = self.client.post(
            REGISTER_URL, _payload(username='res1', email='res1@bcm.edu', role='researcher'),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(User.objects.get(username='res1').role, User.Role.RESEARCHER)

    def test_admin_choice_still_rejected(self):
        """editor/admin 仍是字段级 400（原有行为，不能被这次改动放松）。"""
        for bad in ('admin', 'editor'):
            resp = self.client.post(
                REGISTER_URL, _payload(username=f'u_{bad}', email=f'{bad}@bcm.edu', role=bad),
                format='json')
            self.assertEqual(resp.status_code, 400, f'role={bad} 应 400')

    def test_procurement_cannot_reach_inventory_endpoint(self):
        """端到端确认：自选 procurement 拿不到内部库存写口。"""
        self.client.post(
            REGISTER_URL, _payload(username='pm2', email='pm2@bcm.edu', role='procurement'),
            format='json')
        user = User.objects.get(username='pm2')
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        self.client.force_authenticate(user=user)
        resp = self.client.post('/api/v1/inventory/receipt/', {}, format='json')
        self.assertIn(resp.status_code, (401, 403),
                      f'自选 procurement 的用户不该能调库存入库：{resp.status_code}')


class OrganizationJoinDomainGuardTests(APITestCase):
    """join 必须有不可自助伪造的凭据：机构邮箱域名。"""

    def _org(self, contact_email=''):
        return Organization.objects.create(
            name='Boston Chemistry Lab',
            org_type=Organization.OrgType.ACADEMIC,
            status=Organization.Status.ACTIVE,
            contact_email=contact_email,
            created_by=UserFactory(),
        )

    def _join(self, org, email, username='joiner'):
        return self.client.post(REGISTER_URL, _payload(
            username=username, email=email,
            organization_choice='join', organization_id=org.id,
        ), format='json')

    # ── 正向：同域名放行 ──
    def test_matching_domain_allowed(self):
        org = self._org('pi@bcm.edu')
        resp = self._join(org, 'colleague@bcm.edu')
        self.assertEqual(resp.status_code, 201, resp.content)
        user = User.objects.get(username='joiner')
        self.assertEqual(user.organization_id, org.id)
        self.assertFalse(user.is_org_admin, 'join 进来的人不该自动成为机构管理员')

    def test_domain_match_is_case_insensitive(self):
        org = self._org('PI@BCM.EDU')
        resp = self._join(org, 'Colleague@Bcm.Edu')
        self.assertEqual(resp.status_code, 201, resp.content)

    # ── 反向：这是本组最重要的一半 ──
    def test_different_domain_rejected(self):
        """核心用例：任意人拿公开 org id 就能进 ⇒ 现在必须挡住。"""
        org = self._org('pi@bcm.edu')
        resp = self._join(org, 'attacker@evil.com')
        self.assertEqual(resp.status_code, 400, f'跨域名加入必须拒绝：{resp.content}')
        self.assertFalse(User.objects.filter(username='joiner').exists(),
                         '被拒绝的注册不得留下任何用户行')

    def test_org_without_contact_email_rejected(self):
        """机构没登记邮箱 = 没有可比对的凭据 ⇒ 宁 miss 不错配，拒绝。"""
        org = self._org('')
        resp = self._join(org, 'attacker@evil.com')
        self.assertEqual(resp.status_code, 400)
        # 信封结构：{'success': False, 'data': None, 'meta': {'error': {..., 'details': {...}}}}
        err = resp.json()['meta']['error']
        self.assertIn('organization_id', err.get('details', {}),
                      f'拒绝理由必须落到 organization_id 字段上，实际：{err}')

    def test_public_mailbox_domain_rejected(self):
        """机构拿公共邮箱登记 ⇒ 域名没有排他性，等于没有凭据。"""
        org = self._org('mylab@gmail.com')
        resp = self._join(org, 'attacker@gmail.com')
        self.assertEqual(resp.status_code, 400,
                         '公共邮箱域名不得作为机构归属凭据（谁都能注册同名域名邮箱）')

    def test_rejected_join_does_not_touch_org(self):
        org = self._org('pi@bcm.edu')
        self._join(org, 'attacker@evil.com')
        self.assertEqual(org.members.count(), 0, '被拒绝的 join 不得把人挂进机构')
