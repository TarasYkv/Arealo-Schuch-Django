from django.contrib import admin
from .models import (
    ClawdbotConnection, Project, ProjectMemory, 
    Conversation, ScheduledTask, MemoryFile, Integration
)


@admin.register(ClawdbotConnection)
class ClawdbotConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'status', 'is_active', 'last_seen', 'created_at']
    list_filter = ['status', 'is_active']
    search_fields = ['name', 'user__username']
    readonly_fields = ['last_seen', 'created_at', 'updated_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'connection', 'status', 'priority', 'updated_at']
    list_filter = ['status', 'priority']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProjectMemory)
class ProjectMemoryAdmin(admin.ModelAdmin):
    list_display = ['project', 'entry_type', 'source', 'created_at']
    list_filter = ['entry_type']
    search_fields = ['content', 'source']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'connection', 'channel', 'message_count', 'total_tokens', 'started_at']
    list_filter = ['channel']
    search_fields = ['title', 'summary', 'session_key']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'connection', 'schedule', 'is_enabled', 'next_run']
    list_filter = ['is_enabled']
    search_fields = ['name', 'text']


@admin.register(MemoryFile)
class MemoryFileAdmin(admin.ModelAdmin):
    list_display = ['filename', 'connection', 'path', 'size_bytes', 'last_synced']
    search_fields = ['filename', 'path', 'content']


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    list_display = ['name', 'connection', 'category', 'status', 'last_verified']
    list_filter = ['category', 'status']
    search_fields = ['name', 'notes']
