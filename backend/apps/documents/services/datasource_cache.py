"""DataSourceCache L1 持久化缓存读写 helper。

封装 get/set 语义与源级 TTL，供 L3 容错层成功后写入、L2 Redis 未命中时查询。
TTL 按 docs/DATASOURCE_RELIABILITY.md §5.2 分级：PubChem/ChEMBL 30 天，PubMed 14 天。
"""
import logging
from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone

logger = logging.getLogger(__name__)

# 源级 TTL（秒）。PubMed 元数据会增长故较短；PubChem/ChEMBL 分子结构稳定较长；
# Bioz 文献池会增长但较稳，14 天平衡时效与命中率。
SOURCE_TTL = {
    "pubchem": 60 * 60 * 24 * 30,   # 30 天
    "chembl": 60 * 60 * 24 * 30,    # 30 天
    "pubmed": 60 * 60 * 24 * 14,    # 14 天
    "bioz": 60 * 60 * 24 * 14,      # 14 天
}
DEFAULT_TTL = 60 * 60 * 24 * 14

# 延迟 import 避免启动期循环依赖
def _model():
    from apps.documents.models import DataSourceCache
    return DataSourceCache


def get_cache(source: str, query_key: str, query_namespace: str = "name", allow_stale: bool = False):
    """读取 DataSourceCache。

    命中且未过期 → 返回 data dict；
    过期且 allow_stale → 打点日志后返回命中条目（由调用方标记 is_stale 透传到响应）；
    过期且非 allow_stale → 返回 None；
    未命中 → 返回 None。

    Args:
        source: 数据源标识（pubchem/chembl/pubmed/bioz）
        query_key: 主标识符
        query_namespace: 标识符类型（name/cas/smiles/inchi/inchikey/cid）
        allow_stale: 是否允许返回过期条目（API 失败兜底用）
    """
    if not query_key:
        return None
    try:
        M = _model()
        entry = M.objects.get(source=source, query_key=query_key, query_namespace=query_namespace)
    except M.DoesNotExist:
        return None

    now = timezone.now()
    is_expired = entry.expires_at <= now

    if is_expired:
        if allow_stale:
            logger.info(f"Stale {source} cache used for {query_namespace}:{query_key}")
            return entry
        return None

    return entry


def set_cache(source: str, query_key: str, query_namespace: str, data: dict, ttl_seconds: int | None = None) -> None:
    """写入/更新 DataSourceCache。

    upsert（source + query_key + query_namespace 唯一），刷新 expires_at 与 is_stale=False。
    写入失败静默（缓存是 best-effort 加速层，失败不影响主流程）。
    """
    if not query_key or data is None:
        return
    ttl = ttl_seconds if ttl_seconds is not None else SOURCE_TTL.get(source, DEFAULT_TTL)
    try:
        M = _model()
        defaults = {
            "data_json": __import__("json").dumps(data, ensure_ascii=False),
            "expires_at": timezone.now() + timedelta(seconds=ttl),
            "is_stale": False,
        }
        M.objects.update_or_create(
            source=source,
            query_key=query_key,
            query_namespace=query_namespace,
            defaults=defaults,
        )
    except (IntegrityError, Exception) as e:
        logger.debug(f"DataSourceCache set skipped for {source}:{query_namespace}:{query_key}: {e}")
