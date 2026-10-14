"""E2E 内部采购/销售账号种子（幂等）。

创建「procurement 角色、**非 staff**」的认证用户 —— 用于验证：
  ① 销售在审核台**跨机构可见**所有待审单（2026-10-14 修的 bug）
  ② 销售能审核/备货/发货/开票/收款，但**不能** assign-rep（admin 专属）

★ 关键：`is_staff=False` —— 只有非 staff，才能真正验证 "procurement 也跨机构可见"
（若 is_staff=True，走的是旧的 is_staff 分支，测不出修复）。

运行：
  cd src_claude/backend
  DB_ENGINE=sqlite venv/Scripts/python.exe manage.py shell -c "exec(open('seed_e2e_procurement.py').read())"
"""
from apps.accounts.models import User, Organization
import os

USERNAME = os.environ.get('E2E_PROC_USER', 'e2e_proc')
PASSWORD = os.environ.get('E2E_PROC_PASS', 'E2ePass123!')
ORG_NAME = os.environ.get('E2E_PROC_ORG', 'E2E Supplier Ops')

# 供应商侧运营机构（与客户机构不同 ⇒ 才能验证"跨机构"）
org, _ = Organization.objects.get_or_create(
    name=ORG_NAME,
    defaults={'org_type': 'enterprise', 'country': 'US'},
)

user, created = User.objects.get_or_create(
    username=USERNAME,
    defaults={
        'email': 'e2e_proc@example.com',
        'organization': org,
        'role': 'procurement',
        'is_staff': False,
        'is_superuser': False,
        'email_verified': True,   # ★ 登录要求 email_verified，否则 403
    },
)
# 每轮重跑都重置密码与关键字段，保证幂等且可登录
user.set_password(PASSWORD)
user.organization = org
user.is_staff = False
user.is_superuser = False
user.role = 'procurement'
user.email_verified = True
user.save()

print(f"{'CREATED' if created else 'UPDATED'} "
      f"user={USERNAME} id={user.id} role={user.role} org_id={org.id} is_staff={user.is_staff}")
