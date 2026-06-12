from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.transactions.api.v1.views import (
    OrderViewSet, QuoteViewSet, WishlistViewSet,
)
from apps.transactions.api.v1 import basket_views

router = DefaultRouter()
router.register('orders', OrderViewSet, basename='order')
router.register('quotes', QuoteViewSet, basename='quote')
router.register('wishlist', WishlistViewSet, basename='wishlist')

urlpatterns = [
    # Basket API — explicit views (not router-based) for full control
    path('basket', basket_views.BasketView.as_view(), name='basket-list'),
    path('basket/items', basket_views.AddToBasketView.as_view(), name='basket-add'),
    path('basket/merge', basket_views.MergeBasketView.as_view(), name='basket-merge'),
    path('basket/items/<int:pk>', basket_views.UpdateBasketItemView.as_view(), name='basket-update'),
    path('basket/items/<int:pk>/delete', basket_views.DeleteBasketItemView.as_view(), name='basket-delete'),
    # Remaining router URLs (orders, quotes, wishlist)
    path('', include(router.urls)),
]
