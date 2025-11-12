from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.urls import reverse
from .models import FotogravurImage


def delete_selected_images(modeladmin, request, queryset):
    """
    Custom Admin Action: Mehrere Bilder löschen
    Löscht sowohl die Datenbank-Einträge als auch die Bild-Dateien
    """
    count = queryset.count()

    # Lösche Bild-Dateien und Datenbank-Einträge
    for image in queryset:
        # Lösche S/W-Bild
        if image.image:
            image.image.delete(save=False)
        # Lösche Original-Bild
        if image.original_image:
            image.original_image.delete(save=False)
        # Lösche Datenbank-Eintrag
        image.delete()

    messages.success(request, f'{count} Bild(er) erfolgreich gelöscht (inkl. Dateien).')

delete_selected_images.short_description = "Ausgewählte Bilder löschen (inkl. Dateien)"


@admin.register(FotogravurImage)
class FotogravurImageAdmin(admin.ModelAdmin):
    list_display = [
        'unique_id',
        'image_preview',
        'custom_text_short',
        'shopify_order_id',
        'file_size_display',
        'created_at',
        'edit_link',
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
        'original_image_preview_large',
    ]
    actions = [delete_selected_images]  # Custom Bulk-Delete Action
    fieldsets = (
        ('Verarbeitetes Bild (S/W)', {
            'fields': ('image', 'image_preview_large', 'unique_id', 'original_filename')
        }),
        ('Original-Bild (Farbig)', {
            'fields': ('original_image', 'original_image_preview_large'),
            'classes': ('collapse',),  # Standardmäßig eingeklappt
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
        """Große Bildvorschau im Detail (S/W verarbeitet)"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 600px; max-height: 600px; object-fit: contain; border: 1px solid #ddd; padding: 10px; background: #f8f9fa;" />',
                obj.image.url
            )
        return '-'
    image_preview_large.short_description = 'S/W-Bildvorschau'

    def original_image_preview_large(self, obj):
        """Große Bildvorschau des Originals"""
        if obj.original_image:
            return format_html(
                '<img src="{}" style="max-width: 600px; max-height: 600px; object-fit: contain; border: 1px solid #ddd; padding: 10px; background: #f8f9fa;" />',
                obj.original_image.url
            )
        return '-'
    original_image_preview_large.short_description = 'Original-Bildvorschau'

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

    def edit_link(self, obj):
        """Link zum Bildeditor"""
        if obj.original_image:
            url = reverse('shopify_uploads:image_edit', args=[obj.unique_id])
            return format_html(
                '<a href="{}" class="button" style="padding: 5px 10px; background-color: #17a2b8; color: white; text-decoration: none; border-radius: 4px;">Anpassen</a>',
                url
            )
        return '-'
    edit_link.short_description = 'Bearbeiten'

    def has_add_permission(self, request):
        """Nur über API hochladen, nicht manuell im Admin"""
        return False
