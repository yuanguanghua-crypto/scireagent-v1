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
      username   —— 操作人用户名（模糊）
      model      —— content_type.model（如 product）
      search     —— object_repr 模糊匹配
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
            qs = qs.filter(user__username__icontains=username)

        model = (p.get('model') or '').strip()
        if model:
            qs = qs.filter(content_type__model=model)

        search = (p.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(object_repr__icontains=search))

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
                'models': sorted(
                    AuditLog.objects.values_list('content_type__model', flat=True).distinct()
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
