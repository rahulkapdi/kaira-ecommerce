from django.urls import path
from myapp import views

urlpatterns = [
    # Pages
    path('', views.home, name='home'),
    path('shop/', views.shop, name='shop'),
    path('categories/', views.categories_list, name='categories_list'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),

    # Auth
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),

    # Products
    path('category/<slug:slug>/', views.category_view, name='category'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    # Cart
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/clear/', views.cart_clear, name='cart_clear'),

    # Wishlist
    path('wishlist/', views.wishlist_view, name='wishlist_view'),
    path('wishlist/toggle/<int:product_id>/', views.wishlist_toggle, name='wishlist_toggle'),


    path("test_email/", views.test_email),
    path("checkout/", views.checkout, name="checkout"),
    path("place-order/", views.place_order, name="place_order"),
    path("order-success/<int:order_id>/", views.order_success, name="order_success"),
    path("my-orders/", views.order_history, name="order_history"),
    path("my-orders/<int:order_id>/", views.order_detail, name="order_detail"),
    # path("payment/", views.payment_page, name="payment_page"),  
    # path("payment-success/", views.payment_success, name="payment_success"), 

    path("payment/<int:order_id>/", views.payment_page, name="payment_page"),
    path("payment-success/", views.payment_success, name="payment_success"),

    

]
