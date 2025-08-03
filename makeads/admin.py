from django.contrib import admin
from django.utils.html import format_html
from .models import Campaign, ReferenceImage, Creative, CreativeRevision, AIService, GenerationJob


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'created_at', 'updated_at', 'creative_count']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'description', 'basic_idea']
    readonly_fields = ['created_at', 'updated_at']
    
    def creative_count(self, obj):
        return obj.creatives.count()
    creative_count.short_description = 'Anzahl Creatives'


@admin.register(ReferenceImage)
class ReferenceImageAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'description', 'uploaded_at', 'image_preview']
    list_filter = ['uploaded_at', 'campaign']
    search_fields = ['description', 'campaign__name']
    readonly_fields = ['uploaded_at', 'image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover;" />',
                obj.image.url
            )
        return 'Kein Bild'
    image_preview.short_description = 'Vorschau'


@admin.register(Creative)
class CreativeAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'campaign', 'generation_status', 'generation_batch',
        'is_favorite', 'created_at', 'image_preview'
    ]
    list_filter = [
        'generation_status', 'generation_batch', 'is_favorite',
        'created_at', 'campaign'
    ]
    search_fields = ['title', 'description', 'text_content', 'campaign__name']
    readonly_fields = ['created_at', 'updated_at', 'image_preview']
    list_editable = ['is_favorite', 'generation_status']
    
    def image_preview(self, obj):
        if obj.image_file:
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit: cover;" />',
                obj.image_file.url
            )
        elif obj.image_url:
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit: cover;" />',
                obj.image_url
            )
        return 'Kein Bild'
    image_preview.short_description = 'Vorschau'


@admin.register(CreativeRevision)
class CreativeRevisionAdmin(admin.ModelAdmin):
    list_display = ['original_creative', 'revised_creative', 'created_at']
    list_filter = ['created_at']
    search_fields = ['revision_prompt', 'original_creative__title']
    readonly_fields = ['created_at']


@admin.register(AIService)
class AIServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'service_type', 'is_active', 'default_model', 'max_tokens']
    list_filter = ['service_type', 'is_active']
    search_fields = ['name', 'service_type', 'default_model']
    list_editable = ['is_active']


@admin.register(GenerationJob)
class GenerationJobAdmin(admin.ModelAdmin):
    list_display = [
        'campaign', 'job_type', 'status', 'ai_service',
        'progress', 'created_at', 'started_at', 'completed_at'
    ]
    list_filter = ['job_type', 'status', 'ai_service', 'created_at']
    search_fields = ['campaign__name', 'error_message']
    readonly_fields = ['created_at', 'progress']
    
    def progress(self, obj):
        if obj.target_count > 0:
            percentage = (obj.generated_count / obj.target_count) * 100
            return f"{obj.generated_count}/{obj.target_count} ({percentage:.1f}%)"
        return f"{obj.generated_count}/0"
    progress.short_description = 'Fortschritt'