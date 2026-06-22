"""验证文献推荐器对真实产品的效果"""
import sys, os
sys.path.insert(0, r'E:\scireagent-tencent\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'
sys.stdout.reconfigure(encoding='utf-8')
import django; django.setup()
from apps.commerce.models import Product
from apps.knowledge.services.literature_recommender import LiteratureRecommender

recommender = LiteratureRecommender()

# 测试 5 个代表性产品
test_products = Product.objects.filter(id__in=[53, 63, 21, 33, 37])
# 53=5-Ethynyl-dUTP, 63=2-Azido-dUTP, 21=5-Propargylamino-CTP, 33=Biotin-11-UTP, 37=Cy5-dUTP

for product in test_products:
    print('=' * 65)
    print(f'  [{product.id}] {product.name}')
    print(f'  CAS: {product.cas or "N/A"}')
    print('-' * 65)

    result = recommender.recommend(product, top_k=5)

    apps = result.get("applications", [])
    methods = result.get("methods", [])
    refs = result.get("references", [])

    print(f'  应用场景: {", ".join(apps) if apps else "（来自文献标题提取）"}')
    print(f'  实验方法: {", ".join(methods) if methods else "（来自文献标题提取）"}')
    print(f'  相关文献: {len(refs)} 篇')
    for ref in refs[:3]:
        t = ref["title"]
        if len(t) > 60:
            t = t[:57] + "..."
        print(f'    PMID {ref["pmid"]} | {t}')
    print()

print('=' * 65)
print('  完成')
print('=' * 65)
