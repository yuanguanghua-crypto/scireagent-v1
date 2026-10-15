from django.urls import path

from apps.inventory.api.v1 import views

urlpatterns = [
    # ⚠️ 字面前缀（receipt/movements）必须排在 <int:pk> 之前虽无必要（int 不匹配字母），
    #    但保持可读顺序；list 用带斜杠形式与前端 http.get('/inventory/') 对齐。
    path('inventory/', views.InventoryViewSet.as_view({'get': 'list'}), name='inventory-list'),
    path('inventory/receipt/', views.InventoryReceiptView.as_view(), name='inventory-receipt'),
    path('inventory/movements/', views.InventoryMovementListView.as_view({'get': 'list'}),
         name='inventory-movements'),
    path('inventory/<int:pk>/', views.InventoryViewSet.as_view({'get': 'retrieve'}),
         name='inventory-detail'),
    path('inventory/<int:pk>/adjust/', views.InventoryAdjustView.as_view(), name='inventory-adjust'),
]
