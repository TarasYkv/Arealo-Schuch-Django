from django.contrib import admin
from .models import EmailConfiguration, SuperuserEmailShare, GlobalMessage


@admin.register(EmailConfiguration)
class EmailConfigurationAdmin(admin.ModelAdmin):
    list_display = ['email_host_user', 'smtp_host', 'is_active', 'backend_type', 'created_at']
    list_filter = ['is_active', 'backend_type', 'smtp_use_tls', 'smtp_use_ssl']
    search_fields = ['email_host_user', 'smtp_host', 'default_from_email']
    readonly_fields = ['created_at', 'updated_at', 'masked_password']


@admin.register(SuperuserEmailShare)
class SuperuserEmailShareAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'email_address', 'is_active', 'added_by', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['display_name', 'email_address', 'description']
    readonly_fields = ['created_at']


@admin.register(GlobalMessage)
class GlobalMessageAdmin(admin.ModelAdmin):
    list_display = ['title', 'display_position', 'display_type', 'visibility', 'is_active', 'created_at']
    list_filter = [
        'is_active',
        'display_position',
        'display_type',
        'visibility',
        'is_dismissible',
        'created_at'
    ]
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    fieldsets = (
        ('Nachrichteninhalt', {
            'fields': ('title', 'content')
        }),
        ('Anzeige-Einstellungen', {
            'fields': (
                'display_position',
                'display_type',
                'visibility',
                'duration_seconds',
                'is_dismissible'
            )
        }),
        ('Aktivierung & Zeitplan', {
            'fields': (
                'is_active',
                'start_date',
                'end_date'
            )
        }),
        ('Metadaten', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Nur bei neuen Objekten
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
