from django.contrib import admin
from .models import (
    ShopifyStore, ShopifyProduct, ShopifySyncLog, ProductSEOOptimization,
    ShopifyBackup, BackupItem, RestoreLog
)


@admin.register(ShopifyStore)
class ShopifyStoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop_domain', 'user', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'shop_domain', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Store Information', {
            'fields': ('name', 'shop_domain', 'user', 'is_active')
        }),
        ('API Settings', {
            'fields': ('access_token',),
            'classes': ('collapse',),
        }),
        ('Additional Info', {
            'fields': ('description',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(ShopifyProduct)
class ShopifyProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'store', 'status', 'vendor', 'needs_sync', 'created_at')
    list_filter = ('status', 'needs_sync', 'vendor', 'product_type', 'store')
    search_fields = ('title', 'handle', 'vendor', 'tags')
    readonly_fields = ('shopify_id', 'handle', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Product Information', {
            'fields': ('title', 'body_html', 'vendor', 'product_type', 'status', 'tags')
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description')
        }),
        ('Shopify Data', {
            'fields': ('shopify_id', 'handle', 'store', 'image_url'),
            'classes': ('collapse',),
        }),
        ('Sync Status', {
            'fields': ('needs_sync', 'sync_error'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['mark_needs_sync', 'clear_sync_errors']
    
    def mark_needs_sync(self, request, queryset):
        count = queryset.update(needs_sync=True, sync_error='')
        self.message_user(request, f'{count} Produkte als "Sync erforderlich" markiert.')
    mark_needs_sync.short_description = 'Als "Sync erforderlich" markieren'
    
    def clear_sync_errors(self, request, queryset):
        count = queryset.update(sync_error='')
        self.message_user(request, f'Sync-Fehler für {count} Produkte gelöscht.')
    clear_sync_errors.short_description = 'Sync-Fehler löschen'


@admin.register(ShopifySyncLog)
class ShopifySyncLogAdmin(admin.ModelAdmin):
    list_display = ('store', 'action', 'status', 'products_success', 'products_failed', 'started_at')
    list_filter = ('action', 'status', 'started_at')
    search_fields = ('store__name', 'error_message')
    readonly_fields = ('started_at', 'completed_at')
    
    fieldsets = (
        ('Sync Information', {
            'fields': ('store', 'action', 'status')
        }),
        ('Results', {
            'fields': ('products_success', 'products_failed', 'error_message')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at'),
            'classes': ('collapse',),
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ProductSEOOptimization)
class ProductSEOOptimizationAdmin(admin.ModelAdmin):
    list_display = ('product', 'ai_model', 'keywords_preview', 'is_applied', 'created_at')
    list_filter = ('ai_model', 'is_applied', 'created_at')
    search_fields = ('product__title', 'keywords')
    readonly_fields = ('created_at', 'updated_at', 'ai_response_raw')
    
    fieldsets = (
        ('Produkt', {
            'fields': ('product',)
        }),
        ('SEO-Eingaben', {
            'fields': ('keywords', 'ai_model')
        }),
        ('Original Daten', {
            'fields': ('original_title', 'original_description', 'original_seo_title', 'original_seo_description'),
            'classes': ('collapse',),
        }),
        ('KI-Generierte Daten', {
            'fields': ('generated_seo_title', 'generated_seo_description')
        }),
        ('Status', {
            'fields': ('is_applied', 'ai_prompt_used')
        }),
        ('Debug', {
            'fields': ('ai_response_raw', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def keywords_preview(self, obj):
        keywords = obj.get_keywords_list()
        if keywords:
            preview = ', '.join(keywords[:3])
            if len(keywords) > 3:
                preview += f" (+{len(keywords)-3} weitere)"
            return preview
        return "Keine Keywords"
    keywords_preview.short_description = "Keywords"


# ============================================
# BACKUP & RESTORE ADMIN
# ============================================

class BackupItemInline(admin.TabularInline):
    model = BackupItem
    extra = 0
    readonly_fields = ('item_type', 'shopify_id', 'title', 'created_at')
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ShopifyBackup)
class ShopifyBackupAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'status', 'total_items_count', 'get_size_display', 'created_at')
    list_filter = ('status', 'store', 'created_at')
    search_fields = ('name', 'store__name')
    readonly_fields = (
        'created_at', 'completed_at', 'products_count', 'blogs_count', 'posts_count',
        'collections_count', 'orders_count', 'customers_count', 'pages_count',
        'menus_count', 'redirects_count', 'metafields_count', 'discounts_count',
        'images_count', 'total_size_bytes', 'error_message'
    )
    inlines = [BackupItemInline]

    fieldsets = (
        ('Backup Info', {
            'fields': ('name', 'store', 'user', 'status')
        }),
        ('Backup-Optionen', {
            'fields': (
                'include_products', 'include_product_images',
                'include_blogs', 'include_blog_images',
                'include_collections', 'include_orders', 'include_customers',
                'include_pages', 'include_menus', 'include_redirects',
                'include_metafields', 'include_discounts'
            )
        }),
        ('Statistiken', {
            'fields': (
                'products_count', 'blogs_count', 'posts_count', 'collections_count',
                'orders_count', 'customers_count', 'pages_count', 'menus_count',
                'redirects_count', 'metafields_count', 'discounts_count',
                'images_count', 'total_size_bytes'
            ),
            'classes': ('collapse',),
        }),
        ('Status & Fehler', {
            'fields': ('error_message', 'created_at', 'completed_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(BackupItem)
class BackupItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'item_type', 'backup', 'shopify_id', 'created_at')
    list_filter = ('item_type', 'backup', 'created_at')
    search_fields = ('title', 'shopify_id')
    readonly_fields = ('backup', 'item_type', 'shopify_id', 'title', 'raw_data', 'image_url', 'parent_id', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RestoreLog)
class RestoreLogAdmin(admin.ModelAdmin):
    list_display = ('backup_item', 'status', 'new_shopify_id', 'restored_at')
    list_filter = ('status', 'restored_at')
    search_fields = ('backup_item__title', 'message')
    readonly_fields = ('backup', 'backup_item', 'status', 'new_shopify_id', 'message', 'restored_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
