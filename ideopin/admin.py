from django.contrib import admin
from .models import PinProject, PinSettings, Pin


class PinInline(admin.TabularInline):
    """Inline-Ansicht für Pins innerhalb eines PinProjects"""
    model = Pin
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = ['position', 'overlay_text', 'pin_title', 'pinterest_posted', 'scheduled_at']


@admin.register(PinProject)
class PinProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'keywords_preview', 'status', 'pin_count', 'pin_format', 'created_at']
    list_filter = ['status', 'pin_format', 'pin_count', 'created_at']
    search_fields = ['keywords', 'overlay_text', 'seo_description', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PinInline]

    def keywords_preview(self, obj):
        return obj.keywords[:50] + '...' if len(obj.keywords) > 50 else obj.keywords
    keywords_preview.short_description = 'Keywords'


@admin.register(Pin)
class PinAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'position', 'overlay_text_preview', 'pinterest_posted', 'scheduled_at', 'created_at']
    list_filter = ['pinterest_posted', 'created_at', 'project__user']
    search_fields = ['overlay_text', 'pin_title', 'seo_description', 'project__keywords']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']

    def overlay_text_preview(self, obj):
        return obj.overlay_text[:40] + '...' if len(obj.overlay_text) > 40 else obj.overlay_text
    overlay_text_preview.short_description = 'Overlay-Text'


@admin.register(PinSettings)
class PinSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'default_font', 'default_text_size', 'default_pin_format']
    search_fields = ['user__username']
