from django.urls import path
from apps.quotes.api.v1.views import (
    QuoteRequestQuoteView,
    QuoteRequestCreateView,
    QuoteRequestDetailView,
    QuoteRequestManageListView,
    QuoteRequestCloseView,
    QuoteRequestStartReviewView,
    QuoteRequestRespondView,
    MyQuoteRequestListView,
)

urlpatterns = [
    path('quote-requests/', QuoteRequestCreateView.as_view(), name='quote-request-create'),
    # ★ 顺序无所谓：`<int:pk>` 不会匹配 'manage'（int 转换器只吃数字）
    path(
        'quote-requests/manage/',
        QuoteRequestManageListView.as_view(),
        name='quote-request-manage-list',
    ),
    # ★ 2026-11-27（A-170）：客户自己的询价列表（必须在 `<int:pk>` 之前不会冲突，两者形不同）
    path('quote-requests/mine/', MyQuoteRequestListView.as_view(),
         name='quote-request-mine'),
    path('quote-requests/<int:pk>/', QuoteRequestDetailView.as_view(), name='quote-request-detail'),
    # 运营填写报价 → 状态推进到 quoted + 通知客户（仅内部人员）
    path('quote-requests/<int:pk>/quote/', QuoteRequestQuoteView.as_view(),
         name='quote-request-quote'),
    # ★ 2026-11-26（A-223）：关闭询价（枚举里有 CLOSED，但此前没有任何写入口）
    path('quote-requests/<int:pk>/close/', QuoteRequestCloseView.as_view(),
         name='quote-request-close'),
    # ★ 2026-11-27（A-020，P0）：pending → reviewing。枚举里一直有，但从未有写入口。
    path('quote-requests/<int:pk>/review/', QuoteRequestStartReviewView.as_view(),
         name='quote-request-review'),
    # ★ 2026-11-27（A-264）：客户接受 / 拒绝报价（此前枚举里连终态都没有）
    path('quote-requests/<int:pk>/respond/', QuoteRequestRespondView.as_view(),
         name='quote-request-respond'),
]
