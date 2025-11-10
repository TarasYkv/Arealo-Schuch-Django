from django.contrib import admin
from django.utils.html import format_html
from .models import FotogravurImage


@admin.register(FotogravurImage)
class FotogravurImageAdmin(admin.ModelAdmin):
    list_display = [
        'unique_id',
        'image_preview',
        'custom_text_short',
        'shopify_order_id',
        'file_size_display',
        'created_at',
    ]
    list_filter = ['created_at', 'font_family']
    search_fields = [
        'unique_id',
        'shopify_order_id',
        'shopify_product_id',
        'custom_text',
        'original_filename',
    ]
    readonly_fields = [
        'unique_id',
        'created_at',
        'file_size',
        'uploaded_by',
        'image_preview_large',
    ]
    fieldsets = (
        ('Bild', {
            'fields': ('image', 'image_preview_large', 'unique_id', 'original_filename')
        }),
        ('Shopify Informationen', {
            'fields': ('shopify_order_id', 'shopify_product_id')
        }),
        ('Personalisierung', {
            'fields': ('custom_text', 'font_family', 'processing_settings')
        }),
        ('Metadaten', {
            'fields': ('created_at', 'uploaded_by', 'file_size')
        }),
    )

    def image_preview(self, obj):
        """Kleine Bildvorschau in der Liste"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 100px; object-fit: contain;" />',
                obj.image.url
            )
        return '-'
    image_preview.short_description = 'Vorschau'

    def image_preview_large(self, obj):
        """Große Bildvorschau im Detail"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 600px; max-height: 600px; object-fit: contain; border: 1px solid #ddd; padding: 10px; background: #f8f9fa;" />',
                obj.image.url
            )
        return '-'
    image_preview_large.short_description = 'Bildvorschau'

    def custom_text_short(self, obj):
        """Gekürzter Wunschtext"""
        if obj.custom_text:
            return obj.custom_text[:50] + '...' if len(obj.custom_text) > 50 else obj.custom_text
        return '-'
    custom_text_short.short_description = 'Wunschtext'

    def file_size_display(self, obj):
        """Dateigröße in KB"""
        return f"{obj.file_size_kb} KB" if obj.file_size else '-'
    file_size_display.short_description = 'Dateigröße'

    def has_add_permission(self, request):
        """Nur über API hochladen, nicht manuell im Admin"""
        return False
