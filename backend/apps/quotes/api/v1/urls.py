from django.urls import path
from apps.quotes.api.v1.views import (
    QuoteRequestCreateView,
    QuoteRequestDetailView,
    QuoteRequestManageListView,
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
]
