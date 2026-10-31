"""为可见产品中有 SKU 的配一套**示例**阶梯价（可重复运行）。

⚠️ 这是全量替换：会覆盖这些 SKU 已有的阶梯价。生产已跑过一次（2026-10-31，
23 SKU / 69 档）。再次运行会把这些 SKU 的档位重置为本脚本的规则。

设计依据（商业惯例）：
  - 档位随单价调整：低价试剂批量采购量大，高价试剂批量小
      < $200      → 1 / 10 / 50
      $200-499    → 1 /  5 / 20
      ≥ $500      → 1 /  3 / 10
  - 折扣固定 0% / 5% / 10%，向下取整到整数（商业报价一般不出现零头）
  - 第一档 = 目录价（保证阶梯的起点即标价，客户不会看到"买 1 件反而贵"）

写库路径刻意走真实 view（APIClient 调 PUT /api/v1/skus/<id>/price-tiers/），
而不是直接 ORM —— 这样才会经过后端的 min_qty 唯一校验、单价递减校验、以及 AuditLog。

用法：
  python manage.py shell < _seed_tiers.py          # dry-run，只打印
  ... --apply                                      # 真正写入
"""
import os
import sys
from decimal import Decimal, ROUND_DOWN

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from rest_framework.test import APIClient  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from apps.commerce.models import Product  # noqa: E402

APPLY = '--apply' in sys.argv


def plan(price):
    p = Decimal(str(price))
    if p < 200:
        qtys = (1, 10, 50)
    elif p < 500:
        qtys = (1, 5, 20)
    else:
        qtys = (1, 3, 10)
    offs = (Decimal('1.00'), Decimal('0.95'), Decimal('0.90'))
    out = []
    for q, mult in zip(qtys, offs):
        unit = (p * mult).quantize(Decimal('1'), rounding=ROUND_DOWN) if mult < 1 else p
        out.append({'min_qty': q, 'unit_price': str(unit)})
    # 自检：必须严格递减或持平，否则后端会 400
    for i in range(1, len(out)):
        assert Decimal(out[i]['unit_price']) <= Decimal(out[i - 1]['unit_price']), out
    return out


prods = (Product.objects.filter(status='active', archived=False, is_test_fixture=False)
         .prefetch_related('skus').order_by('catalog_no'))

rows = []
for p in prods:
    for s in p.skus.all():
        tiers = plan(s.price)
        rows.append((p, s, tiers))

print(f'待配置 SKU {len(rows)} 个｜档位合计 {sum(len(t) for _, _, t in rows)}\n')
print(f'{"SKU":<18} {"目录价":>9}  阶梯')
print('-' * 86)
for p, s, tiers in rows:
    desc = ' | '.join(f'≥{t["min_qty"]} → ${float(t["unit_price"]):.0f}' for t in tiers)
    print(f'{s.sku_code:<18} ${float(s.price):>8.2f}  {desc}')

if not APPLY:
    print('\n[dry-run] 未写库。加 --apply 执行。')
    raise SystemExit(0)

admin = get_user_model().objects.filter(is_superuser=True).first()
if not admin:
    print('!! 找不到 superuser，无法通过权限校验')
    raise SystemExit(1)

c = APIClient()
c.force_authenticate(user=admin)

ok = fail = 0
print()
for p, s, tiers in rows:
    r = c.put(f'/api/v1/skus/{s.id}/price-tiers/', {'tiers': tiers},
              format='json', HTTP_HOST='scireagent.com')
    if r.status_code == 200:
        ok += 1
    else:
        fail += 1
        print(f'  !! {s.sku_code} HTTP {r.status_code} {str(r.data)[:160]}')
print(f'写入完成：成功 {ok}｜失败 {fail}')

# 回读校验
from apps.commerce.models import SkuPriceTier  # noqa: E402
print(f'\n库内档位总数 {SkuPriceTier.objects.count()}'
      f'｜覆盖 SKU {SkuPriceTier.objects.values("sku_id").distinct().count()} 个')
