"""CI 用的 E2E 最小种子（幂等）—— 让「空库 + E2E 只读子集」能跑起来。

## 为什么需要它
本地 E2E 跑在一个**有历史数据的开发库**上（127 产品 / 983 订单 / 各种实体），
而 CI 是**全新空库**：页面能打开但列表为空、`/products/66` 直接 404
⇒ 直接照搬 spec 必然大面积失败。本脚本造出**刚好够跑冒烟/a11y/令牌**的最小集。

## 造什么
| 对象 | 用途 |
|---|---|
| `admin`（is_staff + superuser） | `/workspace/*`、`/ops/*` 需要 staff；也是 `E2E_USER` 默认值 |
| `e2e_customer`（researcher, 有 org） | 客户侧页面（`/orders`、`/po/*`） |
| `e2e_proc`（procurement, **非 staff**） | 内部台跨机构可见用例 |
| Organization「E2E Customer Org」 | 客户归属 |
| **Product pk=66**（active + SKU） | ★ 多个 spec 硬编码 `/products/66`，**必须让这个 id 真的存在** |
| 另外 2 个 active 产品 | 列表页（`.product-grid`）非空 |
| 1 张订单（给 customer） | `/orders` 非空 |

## 幂等与安全
- 全部 `get_or_create` + 覆盖关键字段（密码/状态），重复跑结果一致。
- **Product pk=66 只在"不存在"时创建**：本地开发库里 66 号是真实产品（2'-Azido-dATP），
  绝不能覆盖 ⇒ 本地跑本脚本不会动它。
- 订单用固定 `order_no = 'ORD-CI-SEED'`，重复跑不叠加。

运行：
  cd backend
  DB_ENGINE=sqlite venv/Scripts/python.exe manage.py shell -c "exec(open('seed_e2e_ci.py').read())"
"""
from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order

ADMIN_USER = 'admin'
ADMIN_PASS = 'admin123'
CUST_USER = 'e2e_customer'
CUST_PASS = 'E2ePass123!'
PROC_USER = 'e2e_proc'
PROC_PASS = 'E2ePass123!'
ORG_NAME = 'E2E Customer Org'

report = []

# ── 1. 机构 ──
org, created = Organization.objects.get_or_create(
    name=ORG_NAME, defaults={'org_type': 'academic', 'country': 'US'},
)
report.append(f"org={org.id} {'CREATED' if created else 'OK'}")

# ── 2. 账号（密码每轮重置，保证可登录）──
def _user(username, password, role, is_staff, is_super=False, with_org=True):
    u, created = User.objects.get_or_create(username=username)
    u.email = f'{username}@example.com'
    u.organization = org if with_org else None
    u.role = role
    u.is_staff = is_staff
    u.is_superuser = is_super
    u.email_verified = True          # ★ 登录要求已验证，否则 403
    u.set_password(password)
    u.save()
    return u, created

admin, c1 = _user(ADMIN_USER, ADMIN_PASS, 'admin', True, is_super=True)
cust, c2 = _user(CUST_USER, CUST_PASS, 'researcher', False)
proc, c3 = _user(PROC_USER, PROC_PASS, 'procurement', False)
report.append(f"admin={admin.id}{'(new)' if c1 else ''} "
              f"customer={cust.id}{'(new)' if c2 else ''} "
              f"proc={proc.id}{'(new)' if c3 else ''}")

# ── 3. 产品 ──
# ★ pk=66 只在不存在时创建（本地开发库里这是真实产品，不能覆盖）
p66, created66 = Product.objects.get_or_create(
    pk=66,
    defaults={
        'slug': 'e2e-ci-product-66',
        'name': 'E2E CI Product 66',
        'status': Product.Status.ACTIVE,
        # 2026-10-30：新建时即打夹具标记，避免流到前台 /products
        'is_test_fixture': True,
    },
)
if created66:
    SKU.objects.get_or_create(
        sku_code='E2E-CI-SKU-066',
        defaults={'product': p66, 'price': '10.00', 'pack_size': '1 mg'},
    )
report.append(f"product66={p66.id}{'(new)' if created66 else '(已存在，未改动)'}")

for i, slug in enumerate(('e2e-ci-alpha', 'e2e-ci-beta'), start=1):
    p, created = Product.objects.get_or_create(
        slug=slug,
        defaults={'name': f'E2E CI Product {i}', 'status': Product.Status.ACTIVE},
    )
    if created:
        SKU.objects.get_or_create(
            sku_code=f'E2E-CI-SKU-{100 + i}',
            defaults={'product': p, 'price': '12.00', 'pack_size': '5 mg'},
        )
report.append(f"extra_products={Product.objects.filter(slug__startswith='e2e-ci-').count()}")

# ── 4. 一张订单（让 /orders 非空；固定 order_no ⇒ 幂等）──
order, created = Order.objects.get_or_create(
    order_no='ORD-CI-SEED',
    defaults={
        'user': cust,
        'organization': org,
        'po_number': None,
        'status': Order.Status.PO_RECEIVED,
    },
)
report.append(f"order={order.id}{'(new)' if created else ''} status={order.status}")

print('CI_SEED ' + ' | '.join(report))
