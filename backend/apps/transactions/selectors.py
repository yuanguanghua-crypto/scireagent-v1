from .models import Order, Basket, Wishlist


def get_order_detail(order_id):
    """获取订单详情（含明细和关联产品）"""
    return Order.objects.select_related('user').prefetch_related(
        'items__product', 'items__sku'
    ).get(pk=order_id)


def get_user_basket(user):
    """获取用户购物车"""
    return Basket.objects.filter(user=user).select_related('product', 'sku')


def get_user_wishlists(user):
    """获取用户收藏夹"""
    return Wishlist.objects.filter(user=user).prefetch_related('products')
