from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Campaign, AdZone, Advertisement, AdPlacement,
    AdImpression, AdClick, AdSchedule, AdTargeting
)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'status_badge', 'start_date', 'end_date', 'created_by', 'ads_count', 'impressions_count', 'clicks_count', 'daily_limits_display']
    list_filter = ['status', 'start_date', 'end_date', 'created_by']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('name', 'description', 'status', 'created_by')
        }),
        ('Zeitplanung', {
            'fields': ('start_date', 'end_date')
        }),
        ('Impression Limits', {
            'fields': ('daily_impression_limit', 'total_impression_limit'),
            'classes': ('collapse',)
        }),
        ('Click Limits', {
            'fields': ('daily_click_limit', 'total_click_limit'),
            'classes': ('collapse',)
        }),
        ('Metadaten', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'active': 'success',
            'paused': 'warning',
            'completed': 'info'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def ads_count(self, obj):
        return obj.advertisements.count()
    ads_count.short_description = 'Anzeigen'
    
    def impressions_count(self, obj):
        return sum(ad.impressions_count for ad in obj.advertisements.all())
    impressions_count.short_description = 'Impressions'
    
    def clicks_count(self, obj):
        return sum(ad.clicks_count for ad in obj.advertisements.all())
    clicks_count.short_description = 'Klicks'
    
    def daily_limits_display(self, obj):
        imp_limit = obj.daily_impression_limit or '∞'
        click_limit = obj.daily_click_limit or '∞'
        return format_html(
            '<small>Imp: {}<br>Clicks: {}</small>',
            imp_limit, click_limit
        )
    daily_limits_display.short_description = 'Tägl. Limits'


@admin.register(AdZone)
class AdZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'zone_type', 'dimensions', 'max_ads', 'is_active', 'app_restriction']
    list_filter = ['zone_type', 'is_active', 'app_restriction']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('code', 'name', 'description', 'zone_type', 'is_active')
        }),
        ('Dimensionen', {
            'fields': ('width', 'height', 'max_ads')
        }),
        ('Einschränkungen', {
            'fields': ('app_restriction',),
            'classes': ('collapse',)
        }),
        ('Metadaten', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def dimensions(self, obj):
        return f"{obj.width}x{obj.height}px"
    dimensions.short_description = 'Dimensionen'


class AdTargetingInline(admin.StackedInline):
    model = AdTargeting
    extra = 0
    fieldsets = (
        ('Geräte-Targeting', {
            'fields': ('target_desktop', 'target_mobile', 'target_tablet')
        }),
        ('Nutzer-Targeting', {
            'fields': ('target_logged_in', 'target_anonymous')
        }),
        ('App-Targeting', {
            'fields': ('target_apps', 'exclude_apps'),
            'classes': ('collapse',)
        }),
        ('URL-Targeting', {
            'fields': ('target_urls', 'exclude_urls'),
            'classes': ('collapse',)
        }),
    )


class AdScheduleInline(admin.TabularInline):
    model = AdSchedule
    extra = 0
    fields = ['weekday', 'start_time', 'end_time', 'is_active']


class AdPlacementInline(admin.TabularInline):
    model = AdPlacement
    extra = 1
    fields = ['zone', 'priority', 'start_date', 'end_date', 'is_active']


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ['name', 'campaign', 'ad_type', 'status_icon', 'zones_list', 'impressions_count', 'clicks_count', 'ctr_display', 'created_at']
    list_filter = ['ad_type', 'is_active', 'campaign', 'zones']
    search_fields = ['name', 'title', 'description', 'campaign__name']
    readonly_fields = ['id', 'impressions_count', 'clicks_count', 'ctr_display', 'created_at', 'updated_at', 'preview']
    filter_horizontal = ['zones']
    date_hierarchy = 'created_at'
    inlines = [AdPlacementInline, AdScheduleInline, AdTargetingInline]
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('campaign', 'name', 'ad_type', 'is_active', 'weight')
        }),
        ('Inhalt', {
            'fields': ('title', 'description', 'image', 'video_url', 'html_content', 'preview')
        }),
        ('Verlinkung', {
            'fields': ('target_url', 'target_type')
        }),
        ('Platzierung', {
            'fields': ('zones',)
        }),
        ('Statistiken', {
            'fields': ('impressions_count', 'clicks_count', 'ctr_display'),
            'classes': ('collapse',)
        }),
        ('Metadaten', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_icon(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    status_icon.short_description = 'Aktiv'
    
    def zones_list(self, obj):
        zones = obj.zones.all()[:3]
        if zones:
            zone_names = ', '.join([z.name for z in zones])
            if obj.zones.count() > 3:
                zone_names += f' (+{obj.zones.count() - 3})'
            return zone_names
        return '-'
    zones_list.short_description = 'Zonen'
    
    def ctr_display(self, obj):
        return f"{obj.ctr:.2f}%"
    ctr_display.short_description = 'CTR'
    
    def preview(self, obj):
        if obj.ad_type == 'image' and obj.image:
            return mark_safe(f'<img src="{obj.image.url}" style="max-width: 300px; max-height: 200px;" />')
        elif obj.ad_type == 'html' and obj.html_content:
            return mark_safe(f'<div style="border: 1px solid #ddd; padding: 10px; max-width: 300px;">{obj.html_content}</div>')
        elif obj.ad_type == 'text':
            return mark_safe(f'<div style="border: 1px solid #ddd; padding: 10px; max-width: 300px;"><h4>{obj.title}</h4><p>{obj.description}</p></div>')
        return 'Keine Vorschau verfügbar'
    preview.short_description = 'Vorschau'


@admin.register(AdImpression)
class AdImpressionAdmin(admin.ModelAdmin):
    list_display = ['advertisement', 'zone', 'user', 'ip_address', 'page_url', 'timestamp']
    list_filter = ['timestamp', 'zone', 'advertisement__campaign']
    search_fields = ['ip_address', 'page_url', 'user__username', 'advertisement__name']
    readonly_fields = ['advertisement', 'zone', 'user', 'ip_address', 'user_agent', 'page_url', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False


@admin.register(AdClick)
class AdClickAdmin(admin.ModelAdmin):
    list_display = ['advertisement', 'zone', 'user', 'ip_address', 'timestamp']
    list_filter = ['timestamp', 'zone', 'advertisement__campaign']
    search_fields = ['ip_address', 'user__username', 'advertisement__name']
    readonly_fields = ['advertisement', 'zone', 'user', 'ip_address', 'user_agent', 'referrer_url', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
