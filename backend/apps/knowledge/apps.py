import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.knowledge'
    verbose_name = 'Knowledge'

    def ready(self):
        # BioProCorpus 索引预热钩子（可选）。
        # 默认惰性：索引在首次 AI AUTO MATCH 请求时构建一次，之后全进程复用（见
        # apps.knowledge.services.protocol_recommender.get_shared_retriever）。
        # 设环境变量 BIOPROCORPUS_PRELOAD=1 可在启动时预热（生产推荐，首个请求不慢）；
        # 不设则惰性（开发友好，runserver 频繁重启不拖慢）。
        # 详见 docs/DATASOURCE_RELIABILITY.md §7
        if os.getenv('BIOPROCORPUS_PRELOAD') == '1':
            try:
                from apps.knowledge.services.protocol_recommender import get_shared_retriever
                get_shared_retriever()
            except Exception as e:
                logger.warning(f"BioProCorpus preload skipped: {e}")
