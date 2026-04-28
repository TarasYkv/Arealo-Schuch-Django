from django.contrib import admin

from .models import (
    MagvisBlog,
    MagvisImageAsset,
    MagvisProject,
    MagvisReportConfig,
    MagvisSettings,
    MagvisTopicQueue,
)


@admin.register(MagvisSettings)
class MagvisSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'glm_model', 'gemini_image_model', 'auto_run_enabled', 'updated_at')
    search_fields = ('user__username', 'user__email')


@admin.register(MagvisReportConfig)
class MagvisReportConfigAdmin(admin.ModelAdmin):
    list_display = ('user', 'report_email', 'updated_at')
    search_fields = ('user__username', 'report_email')


@admin.register(MagvisTopicQueue)
class MagvisTopicQueueAdmin(admin.ModelAdmin):
    list_display = ('topic', 'user', 'priority', 'status', 'used_at', 'created_at')
    list_filter = ('status', 'user')
    search_fields = ('topic', 'notes')
    list_editable = ('priority', 'status')


@admin.register(MagvisProject)
class MagvisProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'stage', 'progress_pct', 'scheduled_at', 'created_at')
    list_filter = ('stage', 'user')
    search_fields = ('title', 'topic')
    readonly_fields = ('id', 'created_at', 'updated_at', 'task_ids', 'stage_logs')


@admin.register(MagvisBlog)
class MagvisBlogAdmin(admin.ModelAdmin):
    list_display = ('seo_title', 'project', 'shopify_article_id', 'updated_at')
    search_fields = ('seo_title', 'project__title')


@admin.register(MagvisImageAsset)
class MagvisImageAssetAdmin(admin.ModelAdmin):
    list_display = ('title_de', 'project', 'source', 'use_overlay', 'created_at')
    list_filter = ('source', 'use_overlay', 'overlay_method')
    search_fields = ('title_de', 'description_de')
