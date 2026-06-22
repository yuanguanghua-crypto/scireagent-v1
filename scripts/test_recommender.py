"""测试方案推荐器"""
import sys, os
sys.path.insert(0, r'E:\scireagent-tencent\backend')
sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['BIOPROCORPUS_DIR'] = r'E:\scireagent-tencent\backend\data\bioprocorpus'

import django; django.setup()

from apps.knowledge.services.protocol_recommender import ProtocolRecommender

recommender = ProtocolRecommender()

# Check indexer status
print('Indexer size:', recommender.retriever.indexer.size())
print('Sources:', recommender.retriever.indexer.list_sources())

# Test different search terms
for term in ['azido', 'nucleotide', 'click', 'dATP', 'PCR', 'DNA']:
    recs = recommender.recommend(term, top_k=2)
    print(f'\nSearch for "{term}": {len(recs)} results')
    for r in recs:
        print(f'  [{r["relevance_score"]:.1f}] {r["protocol"]["title"]}')
