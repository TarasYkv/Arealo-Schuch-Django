from django.contrib import admin
from .models import Transfer, TransferFile, TransferRecipient, DownloadLog, TransferStatistics

class TransferFileInline(admin.TabularInline):
    model = TransferFile
    extra = 0
    readonly_fields = ('id', 'file_size', 'uploaded_at', 'scan_status')

class TransferRecipientInline(admin.TabularInline):
    model = TransferRecipient
    extra = 0
    readonly_fields = ('notified_at', 'first_download_at', 'download_count')

@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'sender', 'sender_email', 'created_at', 'expires_at', 'total_size', 'is_active')
    list_filter = ('is_active', 'transfer_type', 'created_at', 'expires_at')
    search_fields = ('id', 'title', 'sender__username', 'sender_email', 'message')
    readonly_fields = ('id', 'created_at', 'total_downloads', 'total_size')
    inlines = [TransferFileInline, TransferRecipientInline]
    date_hierarchy = 'created_at'

@admin.register(TransferFile)
class TransferFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'transfer', 'file_size', 'file_type', 'uploaded_at', 'scan_status')
    list_filter = ('scan_status', 'uploaded_at')
    search_fields = ('original_filename', 'transfer__id')
    readonly_fields = ('id', 'file_size', 'uploaded_at')

@admin.register(TransferRecipient)
class TransferRecipientAdmin(admin.ModelAdmin):
    list_display = ('email', 'transfer', 'notified_at', 'first_download_at', 'download_count')
    list_filter = ('notified_at', 'first_download_at')
    search_fields = ('email', 'transfer__id')
    readonly_fields = ('notified_at', 'first_download_at', 'download_count')

@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = ('transfer', 'file', 'downloaded_at', 'ip_address', 'download_completed')
    list_filter = ('download_completed', 'downloaded_at')
    search_fields = ('transfer__id', 'ip_address')
    readonly_fields = ('downloaded_at',)
    date_hierarchy = 'downloaded_at'

@admin.register(TransferStatistics)
class TransferStatisticsAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_transfers', 'total_files', 'total_size', 'total_downloads', 'unique_senders')
    list_filter = ('date',)
    date_hierarchy = 'date'
    readonly_fields = ('date', 'total_transfers', 'total_files', 'total_size', 'total_downloads', 'unique_senders', 'unique_recipients')
