"""
Mail App Admin Configuration
"""
from django.contrib import admin
from .models import EmailAccount, Email, Folder, EmailAttachment, EmailDraft, SyncLog


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = ['email_address', 'user', 'display_name', 'is_active', 'is_default', 'last_sync']
    list_filter = ['is_active', 'is_default', 'sync_enabled', 'created_at']
    search_fields = ['email_address', 'display_name', 'user__username']
    readonly_fields = ['access_token', 'refresh_token', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'email_address', 'display_name')
        }),
        ('Account Settings', {
            'fields': ('is_active', 'is_default', 'sync_enabled', 'last_sync')
        }),
        ('OAuth2 Credentials', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'classes': ('collapse',)
        }),
        ('Email Signature', {
            'fields': ('signature',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ['name', 'account', 'folder_type', 'unread_count', 'total_count']
    list_filter = ['folder_type', 'account']
    search_fields = ['name', 'account__email_address']
    readonly_fields = ['zoho_folder_id', 'created_at', 'updated_at']


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ['subject_truncated', 'from_email', 'account', 'folder', 'sent_at', 'is_read', 'is_starred']
    list_filter = ['is_read', 'is_starred', 'is_important', 'message_type', 'priority', 'sent_at']
    search_fields = ['subject', 'from_email', 'from_name', 'body_text']
    readonly_fields = ['zoho_message_id', 'message_id', 'thread_id', 'created_at', 'updated_at']
    date_hierarchy = 'sent_at'
    
    fieldsets = (
        ('Email Information', {
            'fields': ('account', 'folder', 'subject', 'message_type', 'priority')
        }),
        ('Sender & Recipients', {
            'fields': ('from_email', 'from_name', 'to_emails', 'cc_emails', 'bcc_emails', 'reply_to')
        }),
        ('Content', {
            'fields': ('body_text', 'body_html'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read', 'is_starred', 'is_important', 'is_spam')
        }),
        ('Timestamps', {
            'fields': ('sent_at', 'received_at', 'created_at', 'updated_at')
        }),
        ('Identifiers', {
            'fields': ('zoho_message_id', 'message_id', 'thread_id'),
            'classes': ('collapse',)
        }),
    )
    
    def subject_truncated(self, obj):
        return obj.subject[:50] + "..." if len(obj.subject) > 50 else obj.subject
    subject_truncated.short_description = 'Subject'


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'email_subject', 'content_type', 'file_size_human', 'is_cached']
    list_filter = ['content_type', 'is_cached', 'created_at']
    search_fields = ['filename', 'email__subject']
    readonly_fields = ['zoho_attachment_id', 'file_size_human', 'created_at']
    
    def email_subject(self, obj):
        return obj.email.subject[:30] + "..." if len(obj.email.subject) > 30 else obj.email.subject
    email_subject.short_description = 'Email Subject'


@admin.register(EmailDraft)
class EmailDraftAdmin(admin.ModelAdmin):
    list_display = ['subject_truncated', 'user', 'account', 'is_auto_saved', 'updated_at']
    list_filter = ['is_auto_saved', 'is_forward', 'created_at']
    search_fields = ['subject', 'user__username', 'account__email_address']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Draft Information', {
            'fields': ('user', 'account', 'subject', 'is_auto_saved')
        }),
        ('Recipients', {
            'fields': ('to_emails', 'cc_emails', 'bcc_emails')
        }),
        ('Content', {
            'fields': ('body_text', 'body_html')
        }),
        ('Context', {
            'fields': ('in_reply_to', 'is_forward'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subject_truncated(self, obj):
        return obj.subject[:50] + "..." if len(obj.subject) > 50 else obj.subject
    subject_truncated.short_description = 'Subject'


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['account', 'sync_type', 'status', 'emails_fetched', 'emails_created', 'error_count', 'started_at']
    list_filter = ['sync_type', 'status', 'started_at']
    search_fields = ['account__email_address', 'error_message']
    readonly_fields = ['started_at', 'completed_at', 'sync_duration']
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('Sync Information', {
            'fields': ('account', 'sync_type', 'status')
        }),
        ('Statistics', {
            'fields': ('emails_fetched', 'emails_created', 'emails_updated', 'error_count')
        }),
        ('Details', {
            'fields': ('error_message', 'sync_duration'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at')
        }),
    )