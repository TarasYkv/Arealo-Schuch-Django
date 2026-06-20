from django.contrib import admin
from .models import VoiceRecording


@admin.register(VoiceRecording)
class VoiceRecordingAdmin(admin.ModelAdmin):
    list_display = ('unique_id', 'order_name', 'is_approved', 'is_active',
                    'duration_sec', 'play_count', 'created_at')
    list_filter = ('is_approved', 'is_active', 'created_at')
    search_fields = ('unique_id', 'shopify_order_id', 'order_name', 'sender_name', 'recipient_name')
    readonly_fields = ('unique_id', 'created_at', 'approved_at', 'play_count', 'last_played_at', 'file_size')
