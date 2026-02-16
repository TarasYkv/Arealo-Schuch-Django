"""
Desktop App Manager Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import DesktopApp, AppVersion, DownloadLog, AppScreenshot


class AppScreenshotInline(admin.TabularInline):
    """Inline fuer Screenshots im App-Admin"""
    model = AppScreenshot
    extra = 1
    max_num = 10
    readonly_fields = ('id', 'uploaded_at')
    fields = ('image', 'caption', 'order')


class AppVersionInline(admin.TabularInline):
    """Inline fuer Versionen im App-Admin"""
    model = AppVersion
    extra = 0
    readonly_fields = ('id', 'file_size', 'download_count', 'uploaded_at')
    fields = ('version_name', 'version_code', 'channel', 'is_active', 'is_current_for_channel', 'download_count')
    can_delete = False


@admin.register(DesktopApp)
class DesktopAppAdmin(admin.ModelAdmin):
    """Admin Interface fuer Desktop Apps"""

    list_display = ('name', 'app_identifier', 'created_by', 'is_public', 'version_count', 'total_downloads_display', 'created_at')
    list_filter = ('is_public', 'created_at', 'updated_at')
    search_fields = ('name', 'app_identifier', 'description', 'created_by__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [AppScreenshotInline, AppVersionInline]

    fieldsets = (
        ('Grunddaten', {
            'fields': ('name', 'app_identifier', 'description', 'icon', 'created_by', 'is_public')
        }),
        ('Metadaten', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def version_count(self, obj):
        """Anzahl Versionen"""
        return obj.versions.count()
    version_count.short_description = 'Versionen'

    def total_downloads_display(self, obj):
        """Total Downloads"""
        return obj.total_downloads
    total_downloads_display.short_description = 'Downloads'


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    """Admin Interface fuer App-Versionen"""

    list_display = (
        'version_name', 'app', 'version_code', 'channel',
        'file_size_display', 'download_count', 'is_active',
        'is_current_for_channel', 'uploaded_at'
    )
    list_filter = ('channel', 'is_active', 'is_current_for_channel', 'uploaded_at')
    search_fields = ('version_name', 'app__name', 'app__app_identifier', 'release_notes')
    readonly_fields = ('id', 'file_size', 'file_hash', 'download_count', 'uploaded_at', 'updated_at')
    date_hierarchy = 'uploaded_at'

    fieldsets = (
        ('Version-Info', {
            'fields': ('app', 'version_name', 'version_code', 'channel')
        }),
        ('EXE-Datei', {
            'fields': ('exe_file', 'file_size', 'file_hash', 'min_windows_version')
        }),
        ('Status', {
            'fields': ('is_active', 'is_current_for_channel', 'download_count')
        }),
        ('Details', {
            'fields': ('release_notes',)
        }),
        ('Metadaten', {
            'fields': ('id', 'uploaded_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_current', 'activate_versions', 'deactivate_versions']

    def file_size_display(self, obj):
        """Dateigroesse in MB"""
        if obj.file_size:
            return f"{obj.file_size_mb:.2f} MB"
        return "-"
    file_size_display.short_description = 'Dateigröße'

    def mark_as_current(self, request, queryset):
        """Markiere ausgewaehlte Versionen als aktuelle fuer ihren Channel"""
        count = 0
        for version in queryset:
            AppVersion.objects.filter(
                app=version.app,
                channel=version.channel
            ).update(is_current_for_channel=False)

            version.is_current_for_channel = True
            version.save()
            count += 1

        self.message_user(request, f"{count} Version(en) als aktuell markiert.")
    mark_as_current.short_description = "Als aktuelle Version markieren"

    def activate_versions(self, request, queryset):
        """Aktiviere ausgewaehlte Versionen"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} Version(en) aktiviert.")
    activate_versions.short_description = "Versionen aktivieren"

    def deactivate_versions(self, request, queryset):
        """Deaktiviere ausgewaehlte Versionen"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} Version(en) deaktiviert.")
    deactivate_versions.short_description = "Versionen deaktivieren"


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    """Admin Interface fuer Download-Logs (Read-Only)"""

    list_display = (
        'downloaded_at', 'app_version', 'ip_address',
        'windows_version', 'download_completed'
    )
    list_filter = ('download_completed', 'downloaded_at')
    search_fields = (
        'app_version__version_name',
        'app_version__app__name',
        'ip_address',
    )
    readonly_fields = ('app_version', 'downloaded_at', 'ip_address', 'user_agent', 'windows_version', 'download_completed')
    date_hierarchy = 'downloaded_at'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AppScreenshot)
class AppScreenshotAdmin(admin.ModelAdmin):
    """Admin Interface fuer App Screenshots"""

    list_display = ('app', 'caption', 'order', 'image_preview', 'uploaded_at')
    list_filter = ('app', 'uploaded_at')
    search_fields = ('app__name', 'caption')
    readonly_fields = ('id', 'uploaded_at', 'image_preview_large')
    ordering = ('app', 'order')

    fieldsets = (
        ('Screenshot', {
            'fields': ('app', 'image', 'image_preview_large', 'caption', 'order')
        }),
        ('Metadaten', {
            'fields': ('id', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px; object-fit: cover;" />',
                obj.image.url
            )
        return "-"
    image_preview.short_description = 'Vorschau'

    def image_preview_large(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 300px; max-width: 500px;" />',
                obj.image.url
            )
        return "-"
    image_preview_large.short_description = 'Bildvorschau'
