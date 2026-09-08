from .models import Category, Wishlist
from .cart import Cart


def nav_categories(request):
    return {'nav_categories': Category.objects.all()}


def cart_context(request):
    cart = Cart(request)
    return {
        'cart': cart,
        'cart_count': len(cart),
        'cart_total': cart.get_total(),
    }


def wishlist_context(request):
    if request.user.is_authenticated:
        wishlist_ids = set(
            Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)
        )
    else:
        wishlist_ids = set()
    return {'wishlist_ids': wishlist_ids, 'wishlist_count': len(wishlist_ids)}
