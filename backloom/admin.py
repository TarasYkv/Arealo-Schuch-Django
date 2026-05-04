from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    SearchQuery, BacklinkSource, BacklinkSearch,
    NaturmacherProfile, BioVariant, SubmissionAttempt,
)


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


# ===========================================================================
# Phase 1: Submission-Pipeline Admin
# ===========================================================================


class BioVariantInline(admin.TabularInline):
    model = BioVariant
    extra = 0
    fields = ('length_bucket', 'text', 'use_count', 'last_used_at', 'is_active')
    readonly_fields = ('use_count', 'last_used_at')
    ordering = ('length_bucket', 'use_count')


@admin.register(NaturmacherProfile)
class NaturmacherProfileAdmin(admin.ModelAdmin):
    list_display = ('firma', 'user', 'website', 'email', 'plz', 'ort', 'updated_at')
    search_fields = ('firma', 'user__username', 'email', 'website')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [BioVariantInline]

    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Firma', {
            'fields': ('firma', 'inhaber', 'vorname', 'nachname',
                       'rechtsform', 'ust_id', 'handelsregister'),
        }),
        ('Kontakt', {
            'fields': ('website', 'email', 'email_shop', 'telefon'),
        }),
        ('Adresse', {
            'fields': ('strasse', 'plz', 'ort', 'land'),
        }),
        ('Kategorisierung', {
            'fields': ('kategorie', 'keywords'),
        }),
        ('Default-Login', {
            'fields': ('default_username', 'default_password'),
            'classes': ('collapse',),
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(BioVariant)
class BioVariantAdmin(admin.ModelAdmin):
    list_display = ('profile', 'length_bucket', 'text_preview',
                    'use_count', 'last_used_at', 'is_active')
    list_filter = ('length_bucket', 'is_active', 'profile')
    search_fields = ('text', 'profile__firma')
    readonly_fields = ('use_count', 'last_used_at', 'created_at')
    list_editable = ('is_active',)

    def text_preview(self, obj):
        return obj.text[:100] + ('…' if len(obj.text) > 100 else '')
    text_preview.short_description = 'Bio (Vorschau)'


@admin.register(SubmissionAttempt)
class SubmissionAttemptAdmin(admin.ModelAdmin):
    list_display = ('source_domain', 'status_badge', 'started_at', 'duration_label',
                    'is_verified_live', 'cost_eur', 'live_view_link')
    list_filter = ('status', 'is_dofollow', 'is_verified_live',
                   'captcha_solver_used')
    search_fields = ('source__domain', 'source__url', 'backlink_url',
                     'error_message')
    readonly_fields = ('id', 'created_at', 'updated_at', 'duration_label',
                       'live_view_link', 'step_log_pretty')
    date_hierarchy = 'created_at'
    list_per_page = 50

    fieldsets = (
        ('Übersicht', {
            'fields': ('id', 'source', 'profile', 'bio_variant', 'status'),
        }),
        ('Zeit', {
            'fields': ('started_at', 'completed_at', 'duration_label'),
        }),
        ('Resultat', {
            'fields': ('backlink_url', 'is_dofollow', 'is_verified_live',
                       'last_verified_at', 'anchor_text_used'),
        }),
        ('Browser-Container', {
            'fields': ('container_id', 'novnc_url', 'live_view_link'),
            'classes': ('collapse',),
        }),
        ('Captcha', {
            'fields': ('captcha_solver_used',),
        }),
        ('Log', {
            'fields': ('step_log_pretty', 'error_message'),
        }),
        ('Kosten', {
            'fields': ('cost_eur',),
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def source_domain(self, obj):
        return obj.source.domain
    source_domain.short_description = 'Domain'
    source_domain.admin_order_field = 'source__domain'

    def status_badge(self, obj):
        colors = {
            'queued': '#6c757d',
            'running': '#007bff',
            'needs_manual': '#ff9800',
            'success': '#28a745',
            'failed_captcha': '#dc3545',
            'failed_other': '#dc3545',
            'skipped': '#9e9e9e',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def duration_label(self, obj):
        s = obj.duration_seconds
        if s is None:
            return '-'
        m, sec = divmod(s, 60)
        return f'{m}m {sec}s'
    duration_label.short_description = 'Dauer'

    def live_view_link(self, obj):
        if obj.novnc_url:
            return format_html('<a href="{}" target="_blank">🖥 Live-View öffnen</a>',
                               obj.novnc_url)
        return '-'
    live_view_link.short_description = 'Live-View'

    def step_log_pretty(self, obj):
        if not obj.step_log:
            return '-'
        rows = []
        for entry in obj.step_log[-50:]:
            ts = entry.get('ts', '')[:19].replace('T', ' ')
            level = entry.get('level', 'info')
            msg = entry.get('msg', '')
            ss = entry.get('screenshot', '')
            ss_html = f' <a href="{ss}" target="_blank">📸</a>' if ss else ''
            rows.append(f'<div><code>{ts}</code> [{level}] {msg}{ss_html}</div>')
        return mark_safe('\n'.join(rows))
    step_log_pretty.short_description = 'Schritt-Log (letzte 50)'
