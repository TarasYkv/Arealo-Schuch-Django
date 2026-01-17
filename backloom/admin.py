from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import SearchQuery, BacklinkSource, BacklinkSearch


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('query', 'category', 'priority', 'is_active', 'found_count', 'created_at')
    list_filter = ('category', 'is_active', 'priority')
    search_fields = ('query', 'description')
    list_editable = ('is_active', 'priority')
    ordering = ['-priority', 'query']

    fieldsets = (
        ('Suchbegriff', {
            'fields': ('query', 'description')
        }),
        ('Kategorisierung', {
            'fields': ('category', 'priority', 'is_active')
        }),
    )

    def found_count(self, obj):
        """Anzahl gefundener Quellen mit diesem Suchbegriff"""
        count = obj.found_sources.count()
        if count > 0:
            url = reverse('admin:backloom_backlinksource_changelist') + f'?search_query__id__exact={obj.id}'
            return format_html('<a href="{}">{} Quellen</a>', url, count)
        return '0 Quellen'
    found_count.short_description = 'Gefunden'


@admin.register(BacklinkSource)
class BacklinkSourceAdmin(admin.ModelAdmin):
    list_display = (
        'domain_with_favicon', 'title_short', 'category',
        'quality_badge', 'source_type', 'status_icons', 'last_found'
    )
    list_filter = (
        'category', 'source_type', 'is_processed',
        'is_successful', 'is_rejected', 'quality_score'
    )
    search_fields = ('url', 'domain', 'title', 'description')
    readonly_fields = ('id', 'domain', 'first_found', 'created_at', 'updated_at', 'favicon_url')
    date_hierarchy = 'last_found'
    list_per_page = 50
    actions = ['mark_as_processed', 'mark_as_successful', 'mark_as_rejected', 'reset_status']

    fieldsets = (
        ('URL-Informationen', {
            'fields': ('url', 'domain', 'title', 'description', 'favicon_url')
        }),
        ('Kategorisierung', {
            'fields': ('category', 'source_type', 'search_query')
        }),
        ('Bewertung', {
            'fields': ('quality_score', 'domain_authority')
        }),
        ('Status', {
            'fields': ('is_processed', 'is_successful', 'is_rejected', 'notes')
        }),
        ('Zeitstempel', {
            'fields': ('first_found', 'last_found', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def domain_with_favicon(self, obj):
        """Domain mit Favicon anzeigen"""
        favicon = obj.favicon_url or f"https://www.google.com/s2/favicons?domain={obj.domain}&sz=16"
        return format_html(
            '<img src="{}" width="16" height="16" style="margin-right: 5px;"> {}',
            favicon, obj.domain
        )
    domain_with_favicon.short_description = 'Domain'
    domain_with_favicon.admin_order_field = 'domain'

    def title_short(self, obj):
        """Gekürzter Titel"""
        if obj.title:
            return obj.title[:60] + '...' if len(obj.title) > 60 else obj.title
        return '-'
    title_short.short_description = 'Titel'

    def quality_badge(self, obj):
        """Qualitätsbewertung als Badge"""
        colors = {
            'success': '#28a745',
            'info': '#17a2b8',
            'warning': '#ffc107',
            'danger': '#dc3545'
        }
        color = colors.get(obj.quality_color, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.quality_score
        )
    quality_badge.short_description = 'Qualität'
    quality_badge.admin_order_field = 'quality_score'

    def status_icons(self, obj):
        """Status-Icons anzeigen"""
        icons = []
        if obj.is_processed:
            icons.append('<span title="Bearbeitet" style="color: #17a2b8;">&#10004;</span>')
        if obj.is_successful:
            icons.append('<span title="Erfolgreich" style="color: #28a745;">&#9733;</span>')
        if obj.is_rejected:
            icons.append('<span title="Abgelehnt" style="color: #dc3545;">&#10008;</span>')
        return format_html(' '.join(icons)) if icons else '-'
    status_icons.short_description = 'Status'

    @admin.action(description='Als bearbeitet markieren')
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(is_processed=True)
        self.message_user(request, f'{updated} Quellen als bearbeitet markiert.')

    @admin.action(description='Als erfolgreich markieren')
    def mark_as_successful(self, request, queryset):
        updated = queryset.update(is_successful=True, is_processed=True)
        self.message_user(request, f'{updated} Quellen als erfolgreich markiert.')

    @admin.action(description='Als abgelehnt markieren')
    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(is_rejected=True, is_processed=True)
        self.message_user(request, f'{updated} Quellen als abgelehnt markiert.')

    @admin.action(description='Status zurücksetzen')
    def reset_status(self, request, queryset):
        updated = queryset.update(is_processed=False, is_successful=False, is_rejected=False)
        self.message_user(request, f'Status von {updated} Quellen zurückgesetzt.')


@admin.register(BacklinkSearch)
class BacklinkSearchAdmin(admin.ModelAdmin):
    list_display = (
        'created_at', 'triggered_by', 'status_badge',
        'sources_found', 'new_sources', 'duration_formatted'
    )
    list_filter = ('status', 'triggered_by')
    readonly_fields = (
        'id', 'triggered_by', 'status', 'started_at', 'completed_at',
        'sources_found', 'new_sources', 'updated_sources',
        'error_log', 'progress_log', 'created_at'
    )
    date_hierarchy = 'created_at'
    list_per_page = 25

    fieldsets = (
        ('Übersicht', {
            'fields': ('triggered_by', 'status', 'created_at')
        }),
        ('Zeitstempel', {
            'fields': ('started_at', 'completed_at')
        }),
        ('Statistiken', {
            'fields': ('sources_found', 'new_sources', 'updated_sources')
        }),
        ('Protokoll', {
            'fields': ('progress_log', 'error_log'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        """Status als farbiges Badge"""
        colors = {
            'pending': '#6c757d',
            'running': '#007bff',
            'completed': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#ffc107'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        """Keine manuelle Erstellung erlauben"""
        return False

    def has_change_permission(self, request, obj=None):
        """Keine Bearbeitung erlauben"""
        return False
