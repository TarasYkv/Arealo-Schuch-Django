# streamrec/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import RecordingSession, UserPreferences, StreamRecAnalytics


@admin.register(RecordingSession)
class RecordingSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'duration_formatted', 'streams_count', 'started_at']
    list_filter = ['status', 'video_quality', 'format_used', 'started_at']
    search_fields = ['user__username', 'user__email', 'id']
    readonly_fields = ['id', 'started_at']
    date_hierarchy = 'started_at'
    
    fieldsets = [
        ('Session Information', {
            'fields': ['id', 'user', 'started_at', 'ended_at', 'status']
        }),
        ('Technical Details', {
            'fields': ['streams_used', 'layout_used', 'video_quality', 'audio_quality']
        }),
        ('Recording Metrics', {
            'fields': ['duration_seconds', 'file_size_mb', 'format_used']
        }),
        ('Performance & Feedback', {
            'fields': ['browser_info', 'performance_issues', 'user_rating', 'feedback'],
            'classes': ['collapse']
        })
    ]
    
    def streams_count(self, obj):
        return len(obj.streams_used) if obj.streams_used else 0
    streams_count.short_description = 'Streams'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(UserPreferences) 
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'default_video_quality', 'preferred_layout', 'dark_mode', 'updated_at']
    list_filter = ['default_video_quality', 'dark_mode', 'auto_save_settings', 'analytics_enabled']
    search_fields = ['user__username', 'user__email']
    
    fieldsets = [
        ('Quality Settings', {
            'fields': ['user', 'default_video_quality', 'default_audio_quality']
        }),
        ('Layout & UI', {
            'fields': ['preferred_layout', 'show_notifications', 'dark_mode', 'auto_save_settings']
        }),
        ('Advanced Settings', {
            'fields': ['auto_start_composition', 'include_system_audio', 'preferred_format']
        }),
        ('Privacy', {
            'fields': ['analytics_enabled']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(StreamRecAnalytics)
class StreamRecAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_sessions', 'success_rate', 'avg_duration_formatted', 'most_used_layout']
    list_filter = ['date']
    date_hierarchy = 'date'
    
    readonly_fields = ['date']
    
    fieldsets = [
        ('Usage Metrics', {
            'fields': ['date', 'total_sessions', 'successful_sessions', 'failed_sessions']
        }),
        ('Content Metrics', {
            'fields': ['camera_usage', 'screen_usage', 'multi_stream_usage']
        }),
        ('Performance Metrics', {
            'fields': ['avg_duration_seconds', 'avg_file_size_mb', 'most_used_layout']
        }),
        ('Browser Analytics', {
            'fields': ['browser_stats'],
            'classes': ['collapse']
        })
    ]
    
    def success_rate(self, obj):
        if obj.total_sessions > 0:
            rate = (obj.successful_sessions / obj.total_sessions) * 100
            color = 'green' if rate > 80 else 'orange' if rate > 60 else 'red'
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, rate
            )
        return "0%"
    success_rate.short_description = 'Success Rate'
    
    def avg_duration_formatted(self, obj):
        seconds = int(obj.avg_duration_seconds)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    avg_duration_formatted.short_description = 'Avg Duration'
    
    def changelist_view(self, request, extra_context=None):
        # Add summary statistics to the changelist view
        summary = StreamRecAnalytics.objects.aggregate(
            total_all_sessions=Count('total_sessions'),
            avg_success_rate=Avg('successful_sessions'),
            avg_duration_all=Avg('avg_duration_seconds')
        )
        
        extra_context = extra_context or {}
        extra_context['summary'] = summary
        
        return super().changelist_view(request, extra_context=extra_context)


# Customize admin site header
admin.site.site_header = "StreamRec Administration"
admin.site.site_title = "StreamRec Admin"
admin.site.index_title = "StreamRec Dashboard"