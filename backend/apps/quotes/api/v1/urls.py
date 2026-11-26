from django.urls import path
from apps.quotes.api.v1.views import (
    QuoteRequestQuoteView,
    QuoteRequestCreateView,
    QuoteRequestDetailView,
    QuoteRequestManageListView,
    QuoteRequestCloseView,
)

urlpatterns = [
    path('quote-requests/', QuoteRequestCreateView.as_view(), name='quote-request-create'),
    # ★ 顺序无所谓：`<int:pk>` 不会匹配 'manage'（int 转换器只吃数字）
    path(
        'quote-requests/manage/',
        QuoteRequestManageListView.as_view(),
        name='quote-request-manage-list',
    ),
    path('quote-requests/<int:pk>/', QuoteRequestDetailView.as_view(), name='quote-request-detail'),
    # 运营填写报价 → 状态推进到 quoted + 通知客户（仅内部人员）
    path('quote-requests/<int:pk>/quote/', QuoteRequestQuoteView.as_view(),
         name='quote-request-quote'),
    # ★ 2026-11-26（A-223）：关闭询价（枚举里有 CLOSED，但此前没有任何写入口）
    path('quote-requests/<int:pk>/close/', QuoteRequestCloseView.as_view(),
         name='quote-request-close'),
]
