from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Platform, PostingPlan, PlanningSession, PostContent, 
    PostSchedule, TemplateCategory, PostTemplate
)


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ['name', 'character_limit', 'color_badge', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def color_badge(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">'
            '<i class="{}"></i> {}</span>',
            obj.color, obj.icon, obj.name
        )
    color_badge.short_description = 'Badge Preview'


class PostContentInline(admin.TabularInline):
    model = PostContent
    extra = 0
    fields = ['title', 'post_type', 'character_count', 'priority', 'ai_generated']
    readonly_fields = ['character_count']
    show_change_link = True


class PlanningSessionInline(admin.StackedInline):
    model = PlanningSession
    extra = 0
    fields = ['current_step', 'completed_steps']
    readonly_fields = ['completed_steps']


@admin.register(PostingPlan)
class PostingPlanAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'platform', 'status', 'post_count', 'created_at']
    list_filter = ['status', 'platform', 'created_at']
    search_fields = ['title', 'description', 'user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('title', 'description', 'user', 'platform', 'status')
        }),
        ('Schritt 1: Basis-Setup', {
            'fields': ('user_profile', 'target_audience', 'goals', 'vision'),
            'classes': ('collapse',)
        }),
        ('KI-Strategie-Daten', {
            'fields': ('strategy_data',),
            'classes': ('collapse',)
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PlanningSessionInline, PostContentInline]
    
    def post_count(self, obj):
        count = obj.get_post_count()
        scheduled = obj.get_scheduled_posts_count()
        return format_html(
            '{} Posts <small>({} geplant)</small>',
            count, scheduled
        )
    post_count.short_description = 'Posts'


@admin.register(PlanningSession)
class PlanningSessionAdmin(admin.ModelAdmin):
    list_display = ['posting_plan', 'current_step', 'completed_steps_count', 'updated_at']
    list_filter = ['current_step', 'updated_at']
    search_fields = ['posting_plan__title']
    readonly_fields = ['created_at', 'updated_at']
    
    def completed_steps_count(self, obj):
        return f"{len(obj.completed_steps)}/3"
    completed_steps_count.short_description = 'Fortschritt'


class PostScheduleInline(admin.StackedInline):
    model = PostSchedule
    extra = 0
    fields = ['scheduled_date', 'scheduled_time', 'status', 'notes']


@admin.register(PostContent)
class PostContentAdmin(admin.ModelAdmin):
    list_display = ['title', 'posting_plan', 'post_type', 'character_info', 'priority', 'ai_generated', 'created_at']
    list_filter = ['ai_generated', 'post_type', 'priority', 'posting_plan__platform', 'created_at']
    search_fields = ['title', 'content', 'posting_plan__title']
    ordering = ['-created_at']
    readonly_fields = ['character_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Inhalt', {
            'fields': ('posting_plan', 'title', 'content', 'script')
        }),
        ('Metadaten', {
            'fields': ('post_type', 'priority', 'hashtags', 'call_to_action', 'character_count'),
            'classes': ('collapse',)
        }),
        ('KI-Informationen', {
            'fields': ('ai_generated', 'ai_model_used', 'ai_prompt_used'),
            'classes': ('collapse',)
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PostScheduleInline]
    
    def character_info(self, obj):
        percentage = obj.get_character_limit_percentage()
        limit = obj.posting_plan.platform.character_limit
        
        if percentage > 100:
            color = 'red'
        elif percentage > 80:
            color = 'orange'
        else:
            color = 'green'
            
        return format_html(
            '<span style="color: {};">{}/{} ({}%)</span>',
            color, obj.character_count, limit, int(percentage)
        )
    character_info.short_description = 'Zeichen'


@admin.register(PostSchedule)
class PostScheduleAdmin(admin.ModelAdmin):
    list_display = ['post_content', 'scheduled_datetime_display', 'status', 'is_overdue_display']
    list_filter = ['status', 'scheduled_date', 'scheduled_time']
    search_fields = ['post_content__title', 'notes']
    ordering = ['scheduled_date', 'scheduled_time']
    readonly_fields = ['created_at', 'updated_at', 'is_overdue_display']
    
    fieldsets = (
        ('Terminplanung', {
            'fields': ('post_content', 'scheduled_date', 'scheduled_time', 'status')
        }),
        ('Tracking', {
            'fields': ('notes', 'actual_post_url', 'completion_date'),
            'classes': ('collapse',)
        }),
        ('Information', {
            'fields': ('is_overdue_display', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def scheduled_datetime_display(self, obj):
        return f"{obj.scheduled_date} {obj.scheduled_time}"
    scheduled_datetime_display.short_description = 'Geplant für'
    
    def is_overdue_display(self, obj):
        if obj.is_overdue():
            return format_html('<span style="color: red;">⚠️ Überfällig</span>')
        else:
            return format_html('<span style="color: green;">✅ Pünktlich</span>')
    is_overdue_display.short_description = 'Status'


class PostTemplateInline(admin.TabularInline):
    model = PostTemplate
    extra = 0
    fields = ['name', 'usage_count', 'is_active']
    readonly_fields = ['usage_count']


@admin.register(TemplateCategory)
class TemplateCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform', 'template_count']
    list_filter = ['platform']
    search_fields = ['name', 'description']
    ordering = ['platform', 'name']
    
    inlines = [PostTemplateInline]
    
    def template_count(self, obj):
        return obj.templates.count()
    template_count.short_description = 'Templates'


@admin.register(PostTemplate)
class PostTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'usage_count', 'is_active', 'created_at']
    list_filter = ['category__platform', 'category', 'is_active', 'created_at']
    search_fields = ['name', 'content_template', 'script_template']
    ordering = ['-usage_count', 'name']
    readonly_fields = ['usage_count', 'created_at']
    
    fieldsets = (
        ('Template Info', {
            'fields': ('name', 'category', 'is_active', 'usage_count')
        }),
        ('Template Content', {
            'fields': ('content_template', 'script_template')
        }),
        ('KI-Prompts', {
            'fields': ('ai_system_prompt', 'ai_user_prompt_template'),
            'classes': ('collapse',)
        }),
        ('Statistiken', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
