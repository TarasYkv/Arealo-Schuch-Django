from django.contrib import admin
from .models import ImageProject, ProcessingStep, ExportFormat, EngravingSettings, AIGenerationHistory


@admin.register(ImageProject)
class ImageProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'source_type', 'status', 'created_at', 'updated_at']
    list_filter = ['source_type', 'status', 'created_at']
    search_fields = ['name', 'description', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'get_file_size', 'get_processing_steps_count']
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('user', 'name', 'description', 'status')
        }),
        ('Bildquelle', {
            'fields': ('source_type', 'original_image', 'original_filename')
        }),
        ('KI-Generation', {
            'fields': ('ai_prompt', 'ai_model', 'ai_generation_params'),
            'classes': ('collapse',)
        }),
        ('Verarbeitung', {
            'fields': ('processed_image', 'processing_history', 'current_settings'),
            'classes': ('collapse',)
        }),
        ('Abmessungen', {
            'fields': ('original_width', 'original_height', 'processed_width', 'processed_height'),
            'classes': ('collapse',)
        }),
        ('Metadaten', {
            'fields': ('created_at', 'updated_at', 'get_file_size', 'get_processing_steps_count'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProcessingStep)
class ProcessingStepAdmin(admin.ModelAdmin):
    list_display = ['project', 'operation', 'applied_at', 'processing_time']
    list_filter = ['operation', 'applied_at']
    search_fields = ['project__name', 'operation']
    readonly_fields = ['applied_at']


@admin.register(ExportFormat)
class ExportFormatAdmin(admin.ModelAdmin):
    list_display = ['project', 'format_type', 'quality', 'width', 'height', 'created_at']
    list_filter = ['format_type', 'quality', 'created_at']
    search_fields = ['project__name']


@admin.register(EngravingSettings)
class EngravingSettingsAdmin(admin.ModelAdmin):
    list_display = ['project', 'beam_width', 'line_thickness', 'depth_levels', 'created_at']
    search_fields = ['project__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AIGenerationHistory)
class AIGenerationHistoryAdmin(admin.ModelAdmin):
    list_display = ['prompt_short', 'user', 'ai_model', 'success', 'cost', 'created_at']
    list_filter = ['ai_model', 'success', 'created_at']
    search_fields = ['prompt', 'user__username']
    readonly_fields = ['created_at', 'generation_time']
    
    def prompt_short(self, obj):
        return obj.prompt[:50] + "..." if len(obj.prompt) > 50 else obj.prompt
    prompt_short.short_description = 'Prompt'