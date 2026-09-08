from django.contrib import admin
from .models import *


# ── Category ──────────────────────────────────────────────────────────────────
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


# ── Product extra images (shown inline inside the Product edit page) ──────────
class ProductImageInline(admin.TabularInline):
    """
    This lets you upload extra product images directly on the Product edit page.
    You will see a table of image rows below the main product fields.
    'extra = 4' means 4 empty upload slots are shown by default.
    """
    model  = ProductImage
    extra  = 4                          # number of empty rows shown at once
    fields = ['image', 'caption', 'order']


# ── Product ───────────────────────────────────────────────────────────────────
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display        = ['name', 'category', 'price', 'stock', 'is_available', 'created_at']
    list_filter         = ['category', 'is_available']
    list_editable       = ['price', 'stock', 'is_available']
    prepopulated_fields = {'slug': ('name',)}
    search_fields       = ['name', 'description']
    inlines             = [ProductImageInline]   # ← extra images section


# ── Wishlist ──────────────────────────────────────────────────────────────────
@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display  = ['user', 'product', 'added_at']
    list_filter   = ['user']
    raw_id_fields = ['product']

admin.site.register(Order)
admin.site.register(OrderItem)