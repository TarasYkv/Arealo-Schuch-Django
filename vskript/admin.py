from django.contrib import admin
from .models import VSkriptProject, VSkriptGenerationLog


@admin.register(VSkriptProject)
class VSkriptProjectAdmin(admin.ModelAdmin):
    list_display = ['keyword', 'user', 'script_type', 'tone', 'platform', 'ai_model', 'word_count', 'created_at']
    list_filter = ['script_type', 'tone', 'platform', 'ai_model', 'created_at']
    search_fields = ['keyword', 'title', 'description', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(VSkriptGenerationLog)
class VSkriptGenerationLogAdmin(admin.ModelAdmin):
    list_display = ['project', 'provider', 'model', 'tokens_input', 'tokens_output', 'duration', 'created_at']
    list_filter = ['provider', 'model', 'success', 'created_at']
    search_fields = ['project__keyword', 'model']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
