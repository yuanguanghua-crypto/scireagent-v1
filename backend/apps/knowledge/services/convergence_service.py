# -*- coding: utf-8 -*-
"""收敛类聚合 Service（双层结构 Step 2）。

背景：知识实体粒度爆炸（ResearchGoal 13k / Application 32k，前端全量渲染不可用），
通过"双层结构"解决——数据层保留细粒度实体，展示聚合层提供 851 个收敛类
（静态映射 JSON，无 migration）。本模块负责加载该静态映射并提供只读查询。

设计要点：
- 静态 JSON 模块级单次加载（lru_cache），避免每次请求重读 601KB 文件；
  文件缺失/损坏时 logging.warning 并返回空结果，**绝不抛异常**（前端兜底为空列表）。
- RG 与 Application 主键各自自增会撞车，成员查询必须分表进行。
- 可见性：is_test_fixture=True 的实体对所有身份都不可见；非 staff 仅返回
  status=ACTIVE 的实体，staff 返回全量（含草稿）。
"""
import json
import logging
from functools import lru_cache

from django.conf import settings
from django.db.models import Count

from apps.knowledge.models import Application, ResearchGoal

logger = logging.getLogger(__name__)

# 静态收敛类映射文件（601KB，851 类，无 migration）
_JSON_PATH = settings.BASE_DIR / 'data' / 'convergence_classes.json'


def _validate_classes(classes):
    """结构校验：classes 必须是 dict 列表，且每项含 class_id / entity_ids 字段。

    返回 False 时由 _load_classes 兜底为空列表，避免后续 list_classes /
    get_class 迭代时对字符串/None 调 .get() 抛 AttributeError/TypeError → 500。
    """
    if not isinstance(classes, list):
        return False
    for cls in classes:
        if not isinstance(cls, dict):
            return False
        if 'class_id' not in cls or 'entity_ids' not in cls:
            return False
    return True


@lru_cache(maxsize=1)
def _load_classes():
    """加载静态收敛类 JSON，返回 classes 列表；任何异常返回 []（绝不抛出）。"""
    try:
        with open(_JSON_PATH, encoding='utf-8') as f:
            data = json.load(f)
        classes = data.get('classes', []) or []
        if not _validate_classes(classes):
            # 结构损坏（classes 非 list / 元素非 dict / 缺字段）：兜底为空列表
            logger.warning(
                'convergence classes JSON structure invalid: %s', _JSON_PATH,
            )
            return []
        logger.info('convergence classes loaded: %d (from %s)', len(classes), _JSON_PATH)
        return classes
    except Exception:
        # 文件缺失 / JSON 损坏 / 结构异常：兜底为空列表，前端显示空态而非 500
        logger.warning('convergence classes JSON unavailable: %s', _JSON_PATH, exc_info=True)
        return []


def _decorate(cls):
    """为单个类附加计算字段：size（成员实体数）；avg_cos（非 kmeans 类无该键 → None）。"""
    return {
        **cls,
        'size': len(cls.get('entity_ids') or []),
        'avg_cos': cls.get('avg_cos'),
    }


def list_classes(group=None, source=None, search=None):
    """返回过滤后的类 dict 列表（默认按 size 降序）。

    - group/source：精确过滤
    - search：按类名大小写不敏感子串过滤
    - 每类附带 size = len(entity_ids)；avg_cos 仅 kmeans 类有，其余为 None
    """
    result = []
    for cls in _load_classes():
        if group and cls.get('group') != group:
            continue
        if source and cls.get('source') != source:
            continue
        if search and search.lower() not in (cls.get('name') or '').lower():
            continue
        result.append(_decorate(cls))
    # 默认按 size 降序；size 相同时以 class_id 稳定排序
    result.sort(key=lambda c: (-c['size'], c['class_id']))
    return result


def get_class(class_id):
    """按 class_id 返回单类 dict（含 size/avg_cos），不存在返回 None。"""
    for cls in _load_classes():
        if cls.get('class_id') == class_id:
            return _decorate(cls)
    return None


def get_members(entity_ids, group, *, include_inactive=False):
    """批量查 DB 返回 {entity_id: {'name', 'slug', 'origin', 'n'}}。

    RG 与 Application 主键各自自增会撞车，**必须分表查询**：
    - rg：ResearchGoal 关联数口径为 Count('protocols')（M2M 到 Protocol）
    - ap：Application 关联数口径为 Count('research_goal_collections')
      （ResearchGoal.application_collection M2M 的 related_name）
    可见性：is_test_fixture=True 一律不返回；include_inactive=False 时仅
    status=ACTIVE（非 staff 只读语义），staff 可传 include_inactive=True 看全量。
    """
    entity_ids = list(entity_ids or [])
    if not entity_ids:
        return {}
    if group == 'rg':
        qs = ResearchGoal.objects.filter(id__in=entity_ids).annotate(n=Count('protocols'))
        active = ResearchGoal.Status.ACTIVE
    elif group == 'ap':
        qs = Application.objects.filter(id__in=entity_ids).annotate(
            n=Count('research_goal_collections'),
        )
        active = Application.Status.ACTIVE
    else:
        # 未知 group：无对应表，返回空（调用方只传 rg/ap）
        return {}
    # 测试夹具行对所有身份不可见（与公开读取面契约一致，不提供逃生口）
    qs = qs.filter(is_test_fixture=False)
    if not include_inactive:
        qs = qs.filter(status=active)
    members = {}
    for obj in qs.only('id', 'name', 'slug', 'origin'):
        members[obj.id] = {
            'name': obj.name,
            'slug': obj.slug,
            'origin': obj.origin,
            'n': obj.n,
        }
    return members
