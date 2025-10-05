from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from .models import StorageLog


@admin.register(StorageLog)
class StorageLogAdmin(admin.ModelAdmin):
    """Admin interface for StorageLog"""

    list_display = [
        'id',
        'user_link',
        'app_badge',
        'action_badge',
        'size_display',
        'created_display',
    ]

    list_filter = [
        'app_name',
        'action',
        'created_at',
    ]

    search_fields = [
        'user__username',
        'user__email',
        'metadata',
    ]

    readonly_fields = [
        'user',
        'app_name',
        'action',
        'size_bytes',
        'size_display_detailed',
        'metadata',
        'created_at',
    ]

    date_hierarchy = 'created_at'

    list_per_page = 50

    fieldsets = (
        ('Benutzer-Information', {
            'fields': ('user',)
        }),
        ('Aktion', {
            'fields': ('app_name', 'action', 'created_at')
        }),
        ('Größe', {
            'fields': ('size_bytes', 'size_display_detailed')
        }),
        ('Metadaten', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )

    def user_link(self, obj):
        """Display user as link"""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.id,
            obj.user.username
        )
    user_link.short_description = 'Benutzer'

    def app_badge(self, obj):
        """Display app as colored badge"""
        colors = {
            'videos': '#0d6efd',
            'fileshare': '#198754',
            'streamrec': '#dc3545',
            'shopify': '#ffc107',
            'image_editor': '#6f42c1',
            'organization': '#fd7e14',
            'chat': '#20c997',
            'other': '#6c757d',
        }
        color = colors.get(obj.app_name, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 0.85rem; font-weight: 500;">{}</span>',
            color,
            obj.get_app_name_display()
        )
    app_badge.short_description = 'App'

    def action_badge(self, obj):
        """Display action as colored badge"""
        colors = {
            'upload': '#28a745',
            'delete': '#dc3545',
            'archive': '#ffc107',
            'restore': '#17a2b8',
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 0.85rem; font-weight: 500;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_badge.short_description = 'Aktion'

    def size_display(self, obj):
        """Display size in readable format"""
        mb = obj.get_size_mb()
        if mb >= 1:
            return f"{mb:.2f} MB"
        else:
            return f"{obj.get_size_kb():.2f} KB"
    size_display.short_description = 'Größe'

    def size_display_detailed(self, obj):
        """Display size with all units"""
        mb = obj.get_size_mb()
        kb = obj.get_size_kb()
        return f"{mb:.2f} MB ({kb:.2f} KB / {obj.size_bytes:,} Bytes)"
    size_display_detailed.short_description = 'Größe (Details)'

    def created_display(self, obj):
        """Display formatted creation date"""
        return obj.created_at.strftime('%d.%m.%Y %H:%M:%S')
    created_display.short_description = 'Erstellt'
    created_display.admin_order_field = 'created_at'

    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to changelist view"""
        extra_context = extra_context or {}

        # Total statistics
        queryset = self.get_queryset(request)

        total_stats = queryset.aggregate(
            total_uploads=Count('id', filter=Q(action='upload')),
            total_deletions=Count('id', filter=Q(action='delete')),
            total_uploaded_bytes=Sum('size_bytes', filter=Q(action='upload')),
            total_deleted_bytes=Sum('size_bytes', filter=Q(action='delete')),
        )

        # Per-app statistics
        app_stats = queryset.values('app_name').annotate(
            total=Count('id'),
            total_bytes=Sum('size_bytes')
        ).order_by('-total_bytes')

        extra_context['total_uploads'] = total_stats['total_uploads'] or 0
        extra_context['total_deletions'] = total_stats['total_deletions'] or 0
        extra_context['total_uploaded_mb'] = (total_stats['total_uploaded_bytes'] or 0) / (1024 * 1024)
        extra_context['total_deleted_mb'] = (total_stats['total_deleted_bytes'] or 0) / (1024 * 1024)
        extra_context['app_stats'] = app_stats

        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        """Disable manual adding (logs are auto-created)"""
        return False

    def has_change_permission(self, request, obj=None):
        """Make logs read-only"""
        return False
