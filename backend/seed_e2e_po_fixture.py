"""E2E PO 夹具（幂等）—— 专用 Product/SKU/Inventory + 写夹具文件供 spec 读取。

为什么要它：
  - `POST /orders/{id}/allocate/` 需要 `inventory_id`，而**没有 inventory 查询 API**
    ⇒ spec 无法通过 API 发现 inventory_id。故由本脚本造夹具并把 id 写入 JSON 文件。
  - 用**专用 E2E SKU**（code 前缀 `E2E-PO-`），与真实数据隔离，便于污染四查。

运行：
  cd src_claude/backend
  DB_ENGINE=sqlite venv/Scripts/python.exe manage.py shell -c "exec(open('seed_e2e_po_fixture.py').read())"
"""
import json
import os

from apps.commerce.models import Product, SKU
from apps.inventory.models import Inventory
from apps.transactions.models import Order

# ① 清理上一轮 E2E 订单（幂等重置；E2E- 前缀专属，不碰真实数据）
old = Order.objects.filter(po_number__startswith='E2E-')
n_old = old.count()
if n_old:
    old.delete()
print(f'CLEANED {n_old} old E2E orders')

SKU_CODE = 'E2E-PO-SKU-001'
AVAILABLE = 1000

product, _ = Product.objects.get_or_create(
    slug='e2e-po-product',
    defaults={'name': 'E2E PO Test Product'},
)
# ★ 必须 active：商品 API 的 get_queryset 只返回 status='active'（draft 会被过滤）
#   ⇒ 否则 PoSubmit 页搜不到该商品，UI 提交流程无法选中。
product.name = 'E2E PO Test Product'
product.status = Product.Status.ACTIVE
product.save()
sku, _ = SKU.objects.get_or_create(
    sku_code=SKU_CODE,
    defaults={'product': product, 'price': '10.00', 'pack_size': '1 mg'},
)
sku.product = product
sku.price = '10.00'
sku.pack_size = '1 mg'
sku.save()

inv, _ = Inventory.objects.get_or_create(
    sku=sku, batch=None, location='MAIN',
    defaults={'available': AVAILABLE, 'allocated': 0},
)
# 重置可分配量，保证每轮可重复分配
inv.available = AVAILABLE
inv.allocated = 0
inv.save(update_fields=['available', 'allocated'])

fixture = {
    'product_id': product.id,
    'sku_id': sku.id,
    'sku_code': SKU_CODE,
    'inventory_id': inv.id,
    'unit_price': '10.00',
    'available': AVAILABLE,
}

# 写到 repo 根（spec 从 frontend/e2e 相对路径读取）。
# ⚠ 用 os.getcwd() 而非 __file__ —— 本脚本经 exec(open().read()) 运行，__file__ 不可靠。
out = os.path.abspath(os.path.join(os.getcwd(), '..', 'e2e_po_fixture.json'))
with open(out, 'w', encoding='utf-8') as f:
    json.dump(fixture, f, ensure_ascii=False, indent=2)

print(f'FIXTURE sku_id={sku.id} inventory_id={inv.id} -> {out}')
