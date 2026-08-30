# -*- coding: utf-8 -*-
"""收敛类聚合 API 视图（双层结构 Step 2）。

薄 View → 厚 Service：所有数据访问走 convergence_service，视图只做参数解析、
手动分页、信封封装。纯只读端点，权限 IsAdminOrReadOnly（写=is_staff）。

端点：
- GET /api/v1/convergence-classes/          收敛类列表（默认按 size 降序）
- GET /api/v1/convergence-classes/<class_id> 单类详情 + 分页成员
"""
from rest_framework.views import APIView

from apps.knowledge.services import convergence_service
from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# 列表/详情项的对外输出字段白名单（避免泄露 entity_ids/representative_id 等内部字段）
_ITEM_FIELDS = ('class_id', 'group', 'name', 'source', 'quality', 'size', 'avg_cos')


def _parse_page_params(request):
    """解析 page/page_size；非法值回退默认。page 从 1 起，page_size 上限 100。"""
    try:
        page = int(request.query_params.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1
    try:
        page_size = int(request.query_params.get('page_size', DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        page_size = DEFAULT_PAGE_SIZE
    return page, page_size


def _paginate(items, page, page_size):
    """按 (page, page_size) 切片；越界返回空列表。"""
    start = (page - 1) * page_size
    return items[start:start + page_size]


def _project_item(cls):
    """把服务层类 dict 投影为对外字段白名单。"""
    return {k: cls.get(k) for k in _ITEM_FIELDS}


class ConvergenceClassListView(EnvelopeMixin, APIView):
    """GET /api/v1/convergence-classes/?group=&source=&search=&page=&page_size=

    响应：{success, data: {items, total}, meta: {page, page_size}}
    items 每项含 class_id/group/name/source/quality/size/avg_cos（非 kmeans 类 avg_cos 为 null）。
    """
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        group = request.query_params.get('group') or None
        source = request.query_params.get('source') or None
        search = request.query_params.get('search') or None
        page, page_size = _parse_page_params(request)
        classes = convergence_service.list_classes(group=group, source=source, search=search)
        items = [_project_item(c) for c in _paginate(classes, page, page_size)]
        return self.success_response(
            {'items': items, 'total': len(classes)},
            {'page': page, 'page_size': page_size},
        )


class ConvergenceClassDetailView(EnvelopeMixin, APIView):
    """GET /api/v1/convergence-classes/<str:class_id>/

    响应：{success, data: {class_id, group, name, source, quality, size, avg_cos, members},
           meta: {member_total, page, page_size}}
    成员按静态映射 entity_ids 顺序返回；可见性：匿名/普通用户仅 ACTIVE，
    staff 全量，is_test_fixture 一律不返回（由 service 保证）。
    """
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, class_id):
        cls = convergence_service.get_class(class_id)
        if cls is None:
            return self.error_response(
                f'convergence class {class_id} not found',
                code='not_found',
                status_code=404,
            )
        # staff（已登录且 is_staff）可看全量（含草稿）；其余仅 ACTIVE
        staff = bool(
            request.user and request.user.is_authenticated and request.user.is_staff
        )
        page, page_size = _parse_page_params(request)
        members_map = convergence_service.get_members(
            cls.get('entity_ids'), cls.get('group'), include_inactive=staff,
        )
        # 成员顺序保持静态映射 entity_ids 的顺序（representative 在前），被过滤掉的跳过
        ordered = [
            {'id': eid, **members_map[eid]}
            for eid in (cls.get('entity_ids') or [])
            if eid in members_map
        ]
        data = {**_project_item(cls), 'members': _paginate(ordered, page, page_size)}
        return self.success_response(
            data,
            {'member_total': len(ordered), 'page': page, 'page_size': page_size},
        )
