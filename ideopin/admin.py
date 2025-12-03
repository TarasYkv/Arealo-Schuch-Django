from django.contrib import admin
from .models import PinProject, PinSettings


@admin.register(PinProject)
class PinProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'keywords_preview', 'status', 'pin_format', 'created_at']
    list_filter = ['status', 'pin_format', 'created_at']
    search_fields = ['keywords', 'overlay_text', 'seo_description', 'user__username']
    readonly_fields = ['created_at', 'updated_at']

    def keywords_preview(self, obj):
        return obj.keywords[:50] + '...' if len(obj.keywords) > 50 else obj.keywords
    keywords_preview.short_description = 'Keywords'


@admin.register(PinSettings)
class PinSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'default_font', 'default_text_size', 'default_pin_format']
    search_fields = ['user__username']
