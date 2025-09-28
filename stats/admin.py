from django.contrib import admin
from .models import PageVisit, UserSession, AdClick, DailyStats, PopularPage


@admin.register(PageVisit)
class PageVisitAdmin(admin.ModelAdmin):
    list_display = ('url', 'page_title', 'user', 'ip_address', 'visit_time')
    list_filter = ('visit_time', 'user')
    search_fields = ('url', 'page_title', 'ip_address')
    readonly_fields = ('visit_time',)
    date_hierarchy = 'visit_time'
    ordering = ('-visit_time',)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'user', 'ip_address', 'start_time', 'last_activity', 'page_count', 'duration')
    list_filter = ('start_time', 'user')
    search_fields = ('session_key', 'ip_address')
    readonly_fields = ('start_time', 'duration')
    date_hierarchy = 'start_time'
    ordering = ('-start_time',)

    def duration(self, obj):
        return obj.duration
    duration.short_description = 'Dauer'


@admin.register(AdClick)
class AdClickAdmin(admin.ModelAdmin):
    list_display = ('ad_name', 'campaign_name', 'zone_name', 'user', 'ip_address', 'click_time')
    list_filter = ('click_time', 'campaign_name', 'zone_name', 'user')
    search_fields = ('ad_name', 'campaign_name', 'zone_name', 'ip_address')
    readonly_fields = ('click_time',)
    date_hierarchy = 'click_time'
    ordering = ('-click_time',)


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ('date', 'unique_visitors', 'total_page_views', 'total_ad_clicks', 'avg_session_duration', 'bounce_rate')
    list_filter = ('date',)
    date_hierarchy = 'date'
    ordering = ('-date',)
    readonly_fields = ('date',)


@admin.register(PopularPage)
class PopularPageAdmin(admin.ModelAdmin):
    list_display = ('page_title', 'url', 'view_count', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('page_title', 'url')
    readonly_fields = ('last_updated',)
    ordering = ('-view_count',)
