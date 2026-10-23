from django.urls import path

from apps.notifications.api.v1 import views

urlpatterns = [
    # 系统状态（邮件通道 / 投递队列 / 调度心跳 / DB）
    path('ops/system-status/', views.SystemStatusView.as_view(), name='ops-system-status'),

    # 邮件模板
    path('ops/email-templates/', views.EmailTemplateListView.as_view(),
         name='ops-email-template-list'),
    path('ops/email-templates/<slug:key>/', views.EmailTemplateDetailView.as_view(),
         name='ops-email-template-detail'),
    path('ops/email-templates/<slug:key>/preview/', views.EmailTemplatePreviewView.as_view(),
         name='ops-email-template-preview'),
    path('ops/email-templates/<slug:key>/send-test/', views.EmailTemplateSendTestView.as_view(),
         name='ops-email-template-send-test'),

    # 投递队列
    path('ops/email-outbox/', views.EmailOutboxListView.as_view(), name='ops-email-outbox-list'),
    path('ops/email-outbox/<int:pk>/<str:action>/', views.EmailOutboxActionView.as_view(),
         name='ops-email-outbox-action'),
]
