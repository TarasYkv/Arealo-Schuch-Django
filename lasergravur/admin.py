from django.contrib import admin
from .models import LaserOrder, LaserDesign, LaserSettings


@admin.register(LaserSettings)
class LaserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'shopify_store', 'last_polled_at', 'poll_interval_minutes')
    raw_id_fields = ('user', 'shopify_store')


@admin.register(LaserOrder)
class LaserOrderAdmin(admin.ModelAdmin):
    list_display = ('shopify_order_number', 'shopify_customer_name',
                    'topf_model', 'status', 'created_at')
    list_filter = ('status', 'topf_model')
    search_fields = ('shopify_order_number', 'shopify_customer_name',
                     'shopify_customer_email')
    readonly_fields = ('created_at', 'updated_at', 'shopify_order_id',
                       'shopify_line_item_id', 'raw_properties')


@admin.register(LaserDesign)
class LaserDesignAdmin(admin.ModelAdmin):
    list_display = ('order', 'font', 'icon_id', 'updated_at')
    raw_id_fields = ('order',)
