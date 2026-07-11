"""E2E 测试账号种子（幂等）。

仅创建「普通认证用户」（is_staff=False）供 PO 客户侧 / 我的订单冒烟登录使用。
admin（is_staff）账号沿用既有测试库账号，本脚本不碰。

运行：
  cd src_claude/backend
  DB_ENGINE=sqlite venv/Scripts/python.exe manage.py shell -c "exec(open('seed_e2e_customer.py').read())"
"""
from apps.accounts.models import User, Organization
import os

USERNAME = os.environ.get('E2E_CUSTOMER_USER', 'e2e_customer')
PASSWORD = os.environ.get('E2E_CUSTOMER_PASS', 'E2ePass123!')
ORG_NAME = 'E2E Customer Org'

org, _ = Organization.objects.get_or_create(
    name=ORG_NAME,
    defaults={'org_type': 'academic', 'country': 'US'},
)

user, created = User.objects.get_or_create(
    username=USERNAME,
    defaults={
        'email': 'e2e_customer@example.com',
        'organization': org,
        'role': 'researcher',
        'is_staff': False,
        'is_superuser': False,
    },
)
# 每轮重跑都重置密码与关键字段，保证幂等且可登录
user.set_password(PASSWORD)
user.organization = org
user.is_staff = False
user.is_superuser = False
user.role = 'researcher'
user.save()

print(f"{'CREATED' if created else 'UPDATED'} "
      f"user={USERNAME} id={user.id} org_id={org.id} is_staff={user.is_staff}")
