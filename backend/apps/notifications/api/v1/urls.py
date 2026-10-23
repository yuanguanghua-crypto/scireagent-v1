from django.urls import path

from apps.notifications.api.v1.views import SystemStatusView

urlpatterns = [
    # 运营台「系统状态」—— 邮件通道 / 投递队列 / 调度心跳 / DB
    path('ops/system-status/', SystemStatusView.as_view(), name='ops-system-status'),
]
