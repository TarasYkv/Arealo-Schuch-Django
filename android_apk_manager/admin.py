"""
Android APK Manager Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import AndroidApp, AppVersion, DownloadLog


class AppVersionInline(admin.TabularInline):
    """Inline für Versionen im App-Admin"""
    model = AppVersion
    extra = 0
    readonly_fields = ('id', 'file_size', 'download_count', 'uploaded_at')
    fields = ('version_name', 'version_code', 'channel', 'is_active', 'is_current_for_channel', 'download_count')
    can_delete = False


@admin.register(AndroidApp)
class AndroidAppAdmin(admin.ModelAdmin):
    """Admin Interface für Android Apps"""

    list_display = ('name', 'package_name', 'created_by', 'is_public', 'version_count', 'total_downloads_display', 'created_at')
    list_filter = ('is_public', 'created_at', 'updated_at')
    search_fields = ('name', 'package_name', 'description', 'created_by__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [AppVersionInline]

    fieldsets = (
        ('Grunddaten', {
            'fields': ('name', 'package_name', 'description', 'icon', 'created_by', 'is_public')
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
    """Admin Interface für App-Versionen"""

    list_display = (
        'version_name', 'app', 'version_code', 'channel',
        'file_size_display', 'download_count', 'is_active',
        'is_current_for_channel', 'uploaded_at'
    )
    list_filter = ('channel', 'is_active', 'is_current_for_channel', 'uploaded_at')
    search_fields = ('version_name', 'app__name', 'app__package_name', 'release_notes')
    readonly_fields = ('id', 'file_size', 'download_count', 'uploaded_at', 'updated_at')
    date_hierarchy = 'uploaded_at'

    fieldsets = (
        ('Version-Info', {
            'fields': ('app', 'version_name', 'version_code', 'channel')
        }),
        ('APK-Datei', {
            'fields': ('apk_file', 'file_size', 'min_android_version')
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
        """Dateigröße in MB"""
        if obj.file_size:
            return f"{obj.file_size_mb:.2f} MB"
        return "-"
    file_size_display.short_description = 'Dateigröße'

    def mark_as_current(self, request, queryset):
        """Markiere ausgewählte Versionen als aktuelle für ihren Channel"""
        count = 0
        for version in queryset:
            # Entferne "current" Flag von allen anderen Versionen im selben Channel
            AppVersion.objects.filter(
                app=version.app,
                channel=version.channel
            ).update(is_current_for_channel=False)

            # Setze Flag für diese Version
            version.is_current_for_channel = True
            version.save()
            count += 1

        self.message_user(request, f"{count} Version(en) als aktuell markiert.")
    mark_as_current.short_description = "Als aktuelle Version markieren"

    def activate_versions(self, request, queryset):
        """Aktiviere ausgewählte Versionen"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} Version(en) aktiviert.")
    activate_versions.short_description = "Versionen aktivieren"

    def deactivate_versions(self, request, queryset):
        """Deaktiviere ausgewählte Versionen"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} Version(en) deaktiviert.")
    deactivate_versions.short_description = "Versionen deaktivieren"


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    """Admin Interface für Download-Logs (Read-Only)"""

    list_display = (
        'downloaded_at', 'app_version', 'ip_address',
        'android_version', 'device_model', 'download_completed'
    )
    list_filter = ('download_completed', 'downloaded_at')
    search_fields = (
        'app_version__version_name',
        'app_version__app__name',
        'ip_address',
        'device_model'
    )
    readonly_fields = ('app_version', 'downloaded_at', 'ip_address', 'user_agent', 'android_version', 'device_model', 'download_completed')
    date_hierarchy = 'downloaded_at'

    def has_add_permission(self, request):
        """Keine manuellen Logs erstellen"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Keine Logs löschen"""
        return False

    def has_change_permission(self, request, obj=None):
        """Keine Logs bearbeiten"""
        return False
