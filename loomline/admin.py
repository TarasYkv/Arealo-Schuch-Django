"""
LoomLine Admin - Einfache Admin-Konfiguration
"""

from django.contrib import admin
from .models import Project, TaskEntry


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin für Projekte"""

    list_display = ['name', 'domain', 'owner', 'member_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'domain', 'description', 'owner__username']
    readonly_fields = ['created_at']
    filter_horizontal = ['members']

    fieldsets = (
        ('Projekt-Information', {
            'fields': ('name', 'description', 'domain', 'is_active')
        }),
        ('Benutzer', {
            'fields': ('owner', 'members')
        }),
        ('Zeitstempel', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def member_count(self, obj):
        """Anzahl der Mitglieder anzeigen"""
        return obj.members.count()
    member_count.short_description = 'Mitglieder'


@admin.register(TaskEntry)
class TaskEntryAdmin(admin.ModelAdmin):
    """Admin für erledigte Aufgaben"""

    list_display = ['title', 'project', 'completed_by', 'completed_at', 'created_at']
    list_filter = ['completed_at', 'created_at', 'project']
    search_fields = ['title', 'description', 'project__name', 'completed_by__username']
    readonly_fields = ['created_at']
    autocomplete_fields = ['project', 'completed_by']
    date_hierarchy = 'completed_at'

    fieldsets = (
        ('Aufgaben-Information', {
            'fields': ('title', 'description', 'project')
        }),
        ('Erledigung', {
            'fields': ('completed_by', 'completed_at')
        }),
        ('Zeitstempel', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project', 'completed_by')


# Admin-Site-Konfiguration
admin.site.site_header = "LoomLine Administration"
admin.site.site_title = "LoomLine Admin"
admin.site.index_title = "Projekt Verwaltung"