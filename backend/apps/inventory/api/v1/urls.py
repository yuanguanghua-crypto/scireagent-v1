from django.urls import path

from apps.inventory.api.v1 import views

urlpatterns = [
    # ⚠️ 字面前缀（receipt/movements）必须排在 <int:pk> 之前虽无必要（int 不匹配字母），
    #    但保持可读顺序；list 用带斜杠形式与前端 http.get('/inventory/') 对齐。
    path('inventory/', views.InventoryViewSet.as_view({'get': 'list'}), name='inventory-list'),
    path('inventory/receipt/', views.InventoryReceiptView.as_view(), name='inventory-receipt'),
    path('inventory/movements/', views.InventoryMovementListView.as_view({'get': 'list'}),
         name='inventory-movements'),
    # ★ 2026-10-28（库存数据维护 4a）：显式「纳入库存管理」开关 + 缺口清单。
    #   字面路径必须排在 `inventory/<int:pk>/` 之前（虽然 int 不匹配字母，
    #   将来若有人把 pk 改成 <slug> 就会立刻踩坑）。
    path('inventory/track/', views.InventoryTrackView.as_view(), name='inventory-track'),
    path('inventory/tracked-gaps/', views.TrackedWithoutStockView.as_view(),
         name='inventory-tracked-gaps'),
    # ★ 2026-10-28：缺货拦截告警台。字面路径必须排在 `inventory/<int:pk>/` 之前
    #   （虽然 `<int:pk>` 不匹配字母，顺序仍按可读性保持；将来若改成 `<slug>` 会立刻踩坑）。
    path('inventory/shortage-alerts/', views.StockShortageAlertListView.as_view(),
         name='inventory-shortage-alerts'),
    path('inventory/shortage-alerts/<int:pk>/resolve/', views.StockShortageResolveView.as_view(),
         name='inventory-shortage-resolve'),
    path('inventory/<int:pk>/', views.InventoryViewSet.as_view({'get': 'retrieve'}),
         name='inventory-detail'),
    path('inventory/<int:pk>/adjust/', views.InventoryAdjustView.as_view(), name='inventory-adjust'),
]
