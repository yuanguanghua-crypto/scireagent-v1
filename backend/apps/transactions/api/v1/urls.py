from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.transactions.api.v1.views import (
    OrderViewSet, QuoteViewSet, WishlistViewSet,
)
from apps.transactions.api.v1 import basket_views
from apps.transactions.api.v1.checkout_views import CheckoutView
from apps.transactions.api.v1.admin_order_views import (
    AdminOrderListView, AdminOrderDetailView,
    AdminConfirmOrderView, AdminInvoiceOrderView,
    AdminShipOrderView, AdminCompleteOrderView,
    AdminQuoteOrderView, AdminVerifyPaymentView,
)

router = DefaultRouter()
router.register('orders', OrderViewSet, basename='order')
router.register('quotes', QuoteViewSet, basename='quote')
router.register('wishlist', WishlistViewSet, basename='wishlist')

urlpatterns = [
    # Basket API
    path('basket', basket_views.BasketView.as_view(), name='basket-list'),
    path('basket/items', basket_views.AddToBasketView.as_view(), name='basket-add'),
    path('basket/merge', basket_views.MergeBasketView.as_view(), name='basket-merge'),
    path('basket/items/<int:pk>', basket_views.UpdateBasketItemView.as_view(), name='basket-update'),
    path('basket/items/<int:pk>/delete', basket_views.DeleteBasketItemView.as_view(), name='basket-delete'),

    # Checkout
    path('checkout/', CheckoutView.as_view(), name='checkout'),

    # Admin order management
    path('admin/orders/', AdminOrderListView.as_view(), name='admin-order-list'),
    path('admin/orders/<int:pk>/', AdminOrderDetailView.as_view(), name='admin-order-detail'),
    path('admin/orders/<int:pk>/confirm/', AdminConfirmOrderView.as_view(), name='admin-order-confirm'),
    path('admin/orders/<int:pk>/invoice/', AdminInvoiceOrderView.as_view(), name='admin-order-invoice'),
    path('admin/orders/<int:pk>/ship/', AdminShipOrderView.as_view(), name='admin-order-ship'),
    path('admin/orders/<int:pk>/complete/', AdminCompleteOrderView.as_view(), name='admin-order-complete'),
    path('admin/orders/<int:pk>/quote/', AdminQuoteOrderView.as_view(), name='admin-order-quote'),
    path('admin/invoices/<int:pk>/verify-payment/', AdminVerifyPaymentView.as_view(), name='admin-verify-payment'),

    # Router URLs (orders, quotes, wishlist)
    path('', include(router.urls)),
]
