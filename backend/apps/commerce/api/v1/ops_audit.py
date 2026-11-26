"""运营台「审计日志」—— 只读查询。

## 现状（改动前先读）

`AuditLog`（`apps/commerce/models.py:303`）**只写不读**：全仓只有 `AuditLog.log(...)` 在写，
没有任何查询端点。所以此前要追溯"谁删了这个产品"只能进容器跑 shell。

## 覆盖范围（重要，不要误以为它是全局审计）

**目前只有产品**（Product）的 CREATE / UPDATE / DELETE / RESTORE / HARD_DELETE。
订单、用户、报价、邮件**都不记**。生产实测 123 条记录 100% 是 product。
所以这个页面叫"审计日志"，实际是"产品变更审计"——UI 上如实标注了。

要扩到其它模型，得在对应视图层加 `AuditLog.log(...)` 调用（写在视图层而不是 signal，
因为 signal 拿不到 request.user，这是 DRF 删除漏记的历史根因）。
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from core.permissions import IsAdmin

from apps.commerce.models import AuditLog

logger = logging.getLogger(__name__)


class AuditLogRowSerializer(serializers.ModelSerializer):
    model = serializers.CharField(source='content_type.model', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='')
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    has_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id', 'timestamp', 'action', 'action_display',
            'model', 'object_id', 'object_repr',
            'username', 'has_snapshot',
        ]
        read_only_fields = fields

    def get_has_snapshot(self, obj):
        return bool(obj.snapshot)


class AuditLogListView(EnvelopeMixin, APIView):
    """GET /api/v1/ops/audit-logs/

    参数：
      action     —— CREATE / UPDATE / DELETE / RESTORE / HARD_DELETE
      username   —— 操作人用户名（模糊）；特殊值 `system` 表示「无操作人」那批
                    （`user IS NULL`，UI 把 NULL 显示成 system —— A-165）
      model      —— content_type.model（如 product）
      search     —— 匹配 Object 列：`object_repr` 模糊 + （纯数字时）`object_id` 精确。
                    UI 的 Object 列是 `object_repr` 与 `#object_id` 拼接显示，
                    只搜前者会让「搜编号」永远 0 条 —— A-166
      since/until—— ISO 日期，闭区间
      limit      —— 默认 100，上限 500
    """

    permission_classes = [IsAdmin]

    def get(self, request):
        qs = AuditLog.objects.select_related('user', 'content_type').order_by('-timestamp')
        p = request.query_params

        action = (p.get('action') or '').upper()
        if action in dict(AuditLog.ACTION_CHOICES):
            qs = qs.filter(action=action)

        username = (p.get('username') or '').strip()
        if username:
            # ★ 2026-11-26（A-165）：UI 把「无操作人」渲染成 "system"
            #   （`AuditLogPage.vue:147`：`{{ r.username || 'system' }}`），
            #   但 `user` 为 NULL 的记录 `user__username__icontains='system'` **永远匹配不上**
            #   （NULL 的 join 不产生行）⇒ 输入 system 返回 0 条，
            #   而页面上明明列着那批记录。生产实测（2026-11-26，241 条）：
            #     · `user IS NULL` = **22 条**（正是 QA 说的"22 条 system 记录"）
            #     · `user__username__icontains='system'` = **0 条**
            #   ⇒ 输入 system 时改按 NULL 判定；同时保留 icontains 分支，
            #     万一日后真有人把用户名取成 system_xxx，两种语义都能命中。
            if username.lower() == 'system':
                qs = qs.filter(Q(user__isnull=True) | Q(user__username__icontains=username))
            else:
                qs = qs.filter(user__username__icontains=username)

        model = (p.get('model') or '').strip()
        if model:
            qs = qs.filter(content_type__model=model)

        search = (p.get('search') or '').strip()
        if search:
            # ★ 2026-11-26（A-166）：Object 列在 UI 上是**拼出来**的，不是单一字段。
            #   `AuditLogPage.vue:143-144` 渲染两段：
            #       <span class="al-obj">{{ r.object_repr || '(no name)' }}</span>
            #       <span class="al-oid">#{{ r.object_id }}</span>
            #   ⇒ 运营看到的 "TEST-UTP-20261110-03 #5454" 里，`5454` 是 **object_id**，
            #     `object_repr` 里根本没有 '#'（生产实测 241 条：`object_repr__icontains='#'`
            #     = **0 条**，全部形如 'DS-A043-588100' 这种纯名称）。
            #   而本方法此前只 `object_repr__icontains` ⇒ 搜任何编号后缀都返回 0
            #   （QA 搜 5454 得 0、搜产品名得 26 条，正是这个原因；
            #    生产实测 `object_id=5454` 有 **30 条**审计记录）。
            #   修法：输入是纯数字（可带前导 '#'）时，**同时**按 object_id 精确匹配。
            #   不用 `object_id__icontains` —— 那是整型列转字符串，PG 上会全表隐式转换。
            q = Q(object_repr__icontains=search)
            numeric = search.lstrip('#').strip()
            if numeric.isdigit():
                q |= Q(object_id=int(numeric))
            qs = qs.filter(q)

        since = (p.get('since') or '').strip()
        if since:
            qs = qs.filter(timestamp__date__gte=since)
        until = (p.get('until') or '').strip()
        if until:
            qs = qs.filter(timestamp__date__lte=until)

        try:
            limit = min(int(p.get('limit', 100)), 500)
        except (TypeError, ValueError):
            limit = 100

        total = qs.count()
        rows = AuditLogRowSerializer(qs[:limit], many=True).data
        return self.success_response(rows, meta={
            'pagination': {'count': total, 'limit': limit},
            # UI 要如实告知覆盖范围，否则会被当成"全局审计"
            'coverage': {
                # ★ 必须先 order_by() 清空默认排序再 distinct()：
                #   Meta.ordering = ['-timestamp'] 会让 DISTINCT 变成
                #   DISTINCT(model, timestamp) ⇒ 每条记录都不同，去重完全失效
                #   （实测返回了 123 个重复的 'product'）。
                'models': sorted(
                    set(AuditLog.objects.order_by().values_list(
                        'content_type__model', flat=True))
                ),
                'actions': [c[0] for c in AuditLog.ACTION_CHOICES],
                'note': '只记录产品变更；订单/用户/报价/邮件不在覆盖范围内',
            },
        })


class AuditLogDetailView(EnvelopeMixin, APIView):
    """GET /api/v1/ops/audit-logs/<id>/ — 含快照（变更前/后的字段值）。"""

    permission_classes = [IsAdmin]

    def get(self, request, pk):
        log = AuditLog.objects.select_related('user', 'content_type').filter(pk=pk).first()
        if not log:
            return Response({'detail': 'Audit log not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = AuditLogRowSerializer(log).data
        data['snapshot'] = log.snapshot or {}
        return self.success_response(data)
