from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    ZohoMailServerConnection, 
    EmailTemplateCategory, 
    EmailTemplate, 
    EmailTemplateVersion,
    EmailSendLog,
    EmailTrigger
)


@admin.register(EmailTrigger)
class EmailTriggerAdmin(admin.ModelAdmin):
    list_display = ['name', 'trigger_key', 'category', 'is_active', 'template_count', 'is_system_trigger']
    list_filter = ['category', 'is_active', 'is_system_trigger']
    search_fields = ['name', 'trigger_key', 'description']
    readonly_fields = ['trigger_key', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('name', 'trigger_key', 'description', 'category')
        }),
        ('Status', {
            'fields': ('is_active', 'is_system_trigger')
        }),
        ('Verfügbare Variablen', {
            'fields': ('available_variables',),
            'classes': ('collapse',)
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def template_count(self, obj):
        count = obj.templates.count()
        if count > 0:
            return format_html(
                '<a href="/admin/email_templates/emailtemplate/?trigger__id__exact={}">{} Templates</a>',
                obj.id, count
            )
        return "0 Templates"
    template_count.short_description = "Templates"
    
    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system_trigger:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ZohoMailServerConnection)
class ZohoMailServerConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'email_address', 'region', 'is_active', 'is_configured', 'connection_status', 'created_by', 'created_at']
    list_filter = ['is_active', 'is_configured', 'region', 'created_at']
    search_fields = ['name', 'email_address', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'last_test_success', 'last_error']
    
    fieldsets = (
        ('Grundeinstellungen', {
            'fields': ('name', 'description', 'email_address', 'display_name')
        }),
        ('Zoho Konfiguration', {
            'fields': ('client_id', 'client_secret', 'redirect_uri', 'region')
        }),
        ('OAuth2 Tokens', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'classes': ['collapse']
        }),
        ('Status', {
            'fields': ('is_active', 'is_configured', 'last_test_success', 'last_error')
        }),
        ('Tracking', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def connection_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: red;">Inaktiv</span>')
        elif not obj.is_configured:
            return format_html('<span style="color: orange;">Nicht konfiguriert</span>')
        elif obj.needs_reauth:
            return format_html('<span style="color: orange;">Reauth erforderlich</span>')
        else:
            return format_html('<span style="color: green;">Aktiv</span>')
    connection_status.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailTemplateCategory)
class EmailTemplateCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order', 'template_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']
    
    def template_count(self, obj):
        return obj.templates.count()
    template_count.short_description = 'Anzahl Vorlagen'


class EmailTemplateVersionInline(admin.TabularInline):
    model = EmailTemplateVersion
    extra = 0
    readonly_fields = ['version_number', 'created_by', 'created_at']
    fields = ['version_number', 'change_description', 'created_by', 'created_at']


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'trigger', 'category', 'is_active', 'is_auto_send', 'times_used', 'created_by']
    list_filter = ['template_type', 'trigger__category', 'category', 'is_active', 'is_default', 'is_auto_send', 'created_at']
    search_fields = ['name', 'subject', 'html_content']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['times_used', 'last_used_at', 'created_by', 'last_modified_by', 'created_at', 'updated_at']
    inlines = [EmailTemplateVersionInline]
    
    fieldsets = (
        ('Grundeinstellungen', {
            'fields': ('name', 'slug', 'category', 'template_type')
        }),
        ('Trigger-System', {
            'fields': ('trigger', 'is_auto_send', 'send_delay_minutes', 'conditions'),
            'description': 'Konfiguration des automatischen E-Mail-Versands'
        }),
        ('E-Mail Inhalt', {
            'fields': ('subject', 'html_content', 'text_content')
        }),
        ('Design', {
            'fields': ('use_base_template', 'custom_css'),
            'classes': ['collapse']
        }),
        ('Variablen', {
            'fields': ('available_variables',),
            'classes': ['collapse']
        }),
        ('Status', {
            'fields': ('is_active', 'is_default')
        }),
        ('Statistiken', {
            'fields': ('times_used', 'last_used_at'),
            'classes': ['collapse']
        }),
        ('Tracking', {
            'fields': ('created_by', 'last_modified_by', 'created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailTemplateVersion)
class EmailTemplateVersionAdmin(admin.ModelAdmin):
    list_display = ['template', 'version_number', 'created_by', 'created_at']
    list_filter = ['template', 'created_at']
    search_fields = ['template__name', 'change_description']
    readonly_fields = ['created_by', 'created_at']
    ordering = ['template', '-version_number']


@admin.register(EmailSendLog)
class EmailSendLogAdmin(admin.ModelAdmin):
    list_display = ['recipient_email', 'subject', 'template', 'connection', 'send_status', 'sent_by', 'created_at']
    list_filter = ['is_sent', 'template__template_type', 'connection', 'created_at']
    search_fields = ['recipient_email', 'recipient_name', 'subject']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def send_status(self, obj):
        if obj.is_sent:
            return format_html('<span style="color: green;">✓ Gesendet</span>')
        else:
            return format_html('<span style="color: red;">✗ Fehler</span>')
    send_status.short_description = 'Status'
    
    fieldsets = (
        ('Empfänger', {
            'fields': ('recipient_email', 'recipient_name')
        }),
        ('E-Mail Details', {
            'fields': ('subject', 'template', 'connection')
        }),
        ('Status', {
            'fields': ('is_sent', 'sent_at', 'error_message')
        }),
        ('Kontext', {
            'fields': ('context_data',),
            'classes': ['collapse']
        }),
        ('Tracking', {
            'fields': ('sent_by', 'created_at'),
            'classes': ['collapse']
        }),
    )
