from django.contrib import admin
from .models import BugReport, BugReportAttachment


class BugReportAttachmentInline(admin.TabularInline):
    model = BugReportAttachment
    extra = 0
    readonly_fields = ('uploaded_at', 'file_size', 'content_type')


@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    list_display = ('subject', 'get_sender_name', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'message', 'sender__username', 'sender_name', 'sender_email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [BugReportAttachmentInline]
    
    fieldsets = (
        ('Sender', {
            'fields': ('sender', 'sender_name', 'sender_email')
        }),
        ('Bug-Meldung', {
            'fields': ('subject', 'message', 'status')
        }),
        ('System-Informationen', {
            'fields': ('browser_info', 'url'),
            'classes': ('collapse',)
        }),
        ('Chat-Integration', {
            'fields': ('chat_room',)
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(BugReportAttachment)
class BugReportAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'bug_report', 'file_size', 'is_screenshot', 'uploaded_at')
    list_filter = ('is_screenshot', 'uploaded_at', 'content_type')
    search_fields = ('filename', 'bug_report__subject')
    readonly_fields = ('uploaded_at', 'file_size', 'content_type')