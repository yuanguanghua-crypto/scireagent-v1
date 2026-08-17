"""S4 真实数据平价校验（只读，零写入）。

针对 dev SQLite，断言迁移 0004 后的不变量：
- tier='featured' 行数 == 0          （历史"编辑精选"徽标已清空）
- tier='weak' 行数   == 974         （dev 实测广播/仅语义相似桶）
- 总行数不变                       （零删除，铁律①）
- 所有 weak 行均满足 S_A=0 且 S_B=0  （语义一致：弱相关=广播桶）
- 无"应弱却被标 featured"的残留（S_A=0 & S_B=0 且 tier=featured == 0）

用法：先 `manage.py migrate bridges` 应用 0004，再运行本脚本。
"""
import django
import os
import sys

# 允许以脚本方式直接运行（python scripts/verify_weak_tier_parity.py）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.db.models import Q

from apps.bridges.models import ProductProtocol as M

EXPECTED_WEAK = 974  # dev 实测（S4 规划：974 行 featured 广播桶）

total = M.objects.count()
feat = M.objects.filter(tier='featured').count()
weak = M.objects.filter(tier='weak').count()
document = M.objects.filter(tier='document').count()
literature = M.objects.filter(tier='literature').count()

# weak 行违反语义（本应是广播桶却带正轴A/轴B）
weak_violation = M.objects.filter(tier='weak').filter(
    Q(score_a__gt=0) | Q(score_b__gt=0)
).count()

# 残留：S_A=0 & S_B=0 但仍标 featured（应已被迁移重标）
stale_featured = M.objects.filter(tier='featured').filter(
    Q(score_a=0) | Q(score_a__isnull=True)
).filter(
    Q(score_b=0) | Q(score_b__isnull=True)
).count()

print(f'total={total}')
print(f'tier: document={document} literature={literature} featured={feat} weak={weak}')
print(f'weak_violation(S_A>0|S_B>0)={weak_violation}')
print(f'stale_featured(broadcast but still featured)={stale_featured}')

ok = (
    feat == 0
    and weak == EXPECTED_WEAK
    and weak_violation == 0
    and stale_featured == 0
)
print('PARITY', 'OK' if ok else 'FAIL')
if not ok:
    print(f'  expected weak={EXPECTED_WEAK}, got weak={weak}; featured={feat}')
sys.exit(0 if ok else 1)
