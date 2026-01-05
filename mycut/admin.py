# mycut/admin.py

from django.contrib import admin
from .models import EditProject, TimelineClip, Subtitle, TextOverlay, AIEditSuggestion, ExportJob


class TimelineClipInline(admin.TabularInline):
    model = TimelineClip
    extra = 0
    fields = ['clip_type', 'track_index', 'start_time', 'duration', 'is_muted', 'speed']


class SubtitleInline(admin.TabularInline):
    model = Subtitle
    extra = 0
    fields = ['text', 'start_time', 'end_time', 'is_auto_generated']


class AIEditSuggestionInline(admin.TabularInline):
    model = AIEditSuggestion
    extra = 0
    fields = ['suggestion_type', 'start_time', 'end_time', 'text', 'is_applied', 'is_rejected']


@admin.register(EditProject)
class EditProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'source_video', 'status', 'processing_progress', 'created_at', 'updated_at']
    list_filter = ['status', 'export_quality', 'export_format', 'created_at']
    search_fields = ['name', 'user__username', 'user__email']
    readonly_fields = ['unique_id', 'created_at', 'updated_at']
    inlines = [TimelineClipInline, SubtitleInline, AIEditSuggestionInline]

    fieldsets = (
        ('Projekt', {
            'fields': ('name', 'user', 'source_video', 'output_video', 'unique_id')
        }),
        ('Status', {
            'fields': ('status', 'processing_progress', 'processing_message')
        }),
        ('Export', {
            'fields': ('export_quality', 'export_format', 'estimated_duration')
        }),
        ('Daten', {
            'fields': ('project_data', 'ai_transcription', 'waveform_data'),
            'classes': ('collapse',)
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TimelineClip)
class TimelineClipAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'clip_type', 'track_index', 'start_time', 'duration', 'speed']
    list_filter = ['clip_type', 'is_muted', 'is_hidden']
    search_fields = ['project__name']


@admin.register(Subtitle)
class SubtitleAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'text_preview', 'start_time', 'end_time', 'is_auto_generated', 'confidence']
    list_filter = ['is_auto_generated', 'language']
    search_fields = ['text', 'project__name']

    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Text'


@admin.register(TextOverlay)
class TextOverlayAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'text_preview', 'start_time', 'end_time', 'animation_in']
    list_filter = ['animation_in', 'animation_out']
    search_fields = ['text', 'project__name']

    def text_preview(self, obj):
        return obj.text[:30] + '...' if len(obj.text) > 30 else obj.text
    text_preview.short_description = 'Text'


@admin.register(AIEditSuggestion)
class AIEditSuggestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'suggestion_type', 'text', 'start_time', 'confidence', 'is_applied', 'is_rejected']
    list_filter = ['suggestion_type', 'is_applied', 'is_rejected']
    search_fields = ['text', 'project__name']


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'status', 'progress', 'file_size_display', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['project__name', 'celery_task_id']
    readonly_fields = ['celery_task_id', 'created_at', 'started_at', 'completed_at']

    def file_size_display(self, obj):
        if obj.file_size:
            mb = obj.file_size / (1024 * 1024)
            return f"{mb:.2f} MB"
        return "-"
    file_size_display.short_description = 'Dateigröße'
