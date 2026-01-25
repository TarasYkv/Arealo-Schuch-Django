from django.contrib import admin
from .models import (
    PLoomSettings, ProductTheme, PLoomProduct,
    PLoomProductImage, PLoomProductVariant, PLoomHistory, PLoomFavoritePrice
)


@admin.register(PLoomSettings)
class PLoomSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'ai_provider', 'ai_model', 'writing_style', 'default_store']
    list_filter = ['ai_provider', 'writing_style']
    search_fields = ['user__username']


@admin.register(ProductTheme)
class ProductThemeAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_default', 'default_price', 'created_at']
    list_filter = ['is_default', 'user']
    search_fields = ['name', 'user__username']


class PLoomProductImageInline(admin.TabularInline):
    model = PLoomProductImage
    extra = 0
    fields = ['source', 'position', 'is_featured', 'alt_text']


class PLoomProductVariantInline(admin.TabularInline):
    model = PLoomProductVariant
    extra = 0
    fields = ['option1_name', 'option1_value', 'price', 'sku', 'inventory_quantity']


@admin.register(PLoomProduct)
class PLoomProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'price', 'shopify_store', 'created_at']
    list_filter = ['status', 'user', 'shopify_store']
    search_fields = ['title', 'user__username', 'tags']
    readonly_fields = ['id', 'created_at', 'updated_at', 'uploaded_at']
    inlines = [PLoomProductImageInline, PLoomProductVariantInline]

    fieldsets = (
        ('Basis', {
            'fields': ('id', 'user', 'theme', 'status')
        }),
        ('Produktdaten', {
            'fields': ('title', 'description', 'vendor', 'product_type', 'tags')
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description')
        }),
        ('Preise', {
            'fields': ('price', 'compare_at_price')
        }),
        ('Metafelder', {
            'fields': ('product_metafields', 'category_metafields'),
            'classes': ('collapse',)
        }),
        ('Collection', {
            'fields': ('collection_id', 'collection_name')
        }),
        ('Shopify', {
            'fields': ('shopify_store', 'shopify_product_id', 'upload_error', 'uploaded_at')
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PLoomProductImage)
class PLoomProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'source', 'position', 'is_featured', 'created_at']
    list_filter = ['source', 'is_featured']
    search_fields = ['product__title', 'alt_text']


@admin.register(PLoomProductVariant)
class PLoomProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'title', 'sku', 'price', 'inventory_quantity', 'position']
    list_filter = ['product__user']
    search_fields = ['product__title', 'sku', 'title']


@admin.register(PLoomHistory)
class PLoomHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'field_type', 'content_preview', 'is_selected', 'created_at']
    list_filter = ['field_type', 'is_selected', 'user']
    search_fields = ['content', 'user__username']

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Inhalt'


@admin.register(PLoomFavoritePrice)
class PLoomFavoritePriceAdmin(admin.ModelAdmin):
    list_display = ['user', 'price', 'label', 'usage_count', 'created_at']
    list_filter = ['user']
    search_fields = ['user__username', 'label']
