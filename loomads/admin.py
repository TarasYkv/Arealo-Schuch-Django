from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Campaign, AdZone, Advertisement, AdPlacement,
    AdImpression, AdClick, AdSchedule, AdTargeting,
    AppCampaign, AppAdvertisement, SimpleAd
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


# Import Auto-Campaign Admin Classes
from .admin_auto import *

# Import App-Campaign Admin Classes
from .admin_app import *


@admin.register(AdClick)
class AdClickAdmin(admin.ModelAdmin):
    list_display = ['advertisement', 'zone', 'user', 'ip_address', 'timestamp']
    list_filter = ['timestamp', 'zone', 'advertisement__campaign']
    search_fields = ['ip_address', 'user__username', 'advertisement__name']
    readonly_fields = ['advertisement', 'zone', 'user', 'ip_address', 'user_agent', 'referrer_url', 'timestamp']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False


# =============================================================================
# SIMPLE ADS - Vereinfachtes Admin-Interface
# =============================================================================

@admin.register(SimpleAd)
class SimpleAdAdmin(admin.ModelAdmin):
    """
    Einfaches Admin-Interface für globale Anzeigen.
    Alle Felder übersichtlich auf einer Seite.
    """

    list_display = [
        'preview_thumbnail',
        'title',
        'status_badge',
        'style_badge',
        'stats_display',
        'weight',
        'created_at'
    ]
    list_filter = ['is_active', 'template_style', 'color_scheme']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'impressions', 'clicks', 'ctr_display', 'created_at', 'updated_at', 'preview_large']
    list_editable = ['weight']
    ordering = ['-created_at']

    fieldsets = (
        ('📝 Inhalt', {
            'fields': ('title', 'description', 'image', 'button_text', 'target_url', 'open_in_new_tab'),
            'description': 'Was soll in der Anzeige stehen?'
        }),
        ('🎨 Design', {
            'fields': ('template_style', 'color_scheme', 'custom_color'),
            'description': 'Wie soll die Anzeige aussehen?'
        }),
        ('⚙️ Einstellungen', {
            'fields': ('is_active', 'weight'),
            'description': 'Wann und wie oft soll die Anzeige erscheinen?'
        }),
        ('📊 Statistiken', {
            'fields': ('impressions', 'clicks', 'ctr_display'),
            'classes': ('collapse',),
            'description': 'Performance der Anzeige'
        }),
        ('🔧 Erweitert', {
            'fields': ('exclude_zones', 'id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'Erweiterte Optionen'
        }),
        ('👁️ Vorschau', {
            'fields': ('preview_large',),
            'description': 'So sieht die Anzeige aus'
        }),
    )

    def preview_thumbnail(self, obj):
        """Kleines Vorschaubild in der Liste"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 60px; max-height: 40px; '
                'object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        color = obj.get_primary_color()
        return format_html(
            '<div style="width: 60px; height: 40px; background: {}; '
            'border-radius: 4px; display: flex; align-items: center; '
            'justify-content: center; color: white; font-size: 10px;">Ad</div>',
            color
        )
    preview_thumbnail.short_description = ''

    def status_badge(self, obj):
        """Status-Badge mit Farbe"""
        if obj.is_active:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 3px 8px; '
                'border-radius: 12px; font-size: 11px;">✓ Aktiv</span>'
            )
        return format_html(
            '<span style="background: #6b7280; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 11px;">○ Inaktiv</span>'
        )
    status_badge.short_description = 'Status'

    def style_badge(self, obj):
        """Design-Stil Badge"""
        color = obj.get_primary_color()
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 11px;">{}</span>',
            color, obj.get_template_style_display()
        )
    style_badge.short_description = 'Design'

    def stats_display(self, obj):
        """Impressions, Clicks und CTR in einer Spalte"""
        ctr = obj.ctr
        ctr_color = '#10b981' if ctr >= 2 else ('#f59e0b' if ctr >= 1 else '#6b7280')
        return format_html(
            '<span style="font-size: 12px;">'
            '👁 {} &nbsp; 🖱 {} &nbsp; '
            '<span style="color: {};">📈 {}%</span></span>',
            obj.impressions, obj.clicks, ctr_color, ctr
        )
    stats_display.short_description = 'Performance'

    def ctr_display(self, obj):
        """CTR als lesbarer Wert"""
        return f"{obj.ctr}%"
    ctr_display.short_description = 'Click-Through-Rate'

    def preview_large(self, obj):
        """Große Vorschau der Anzeige"""
        color = obj.get_primary_color()
        style = obj.template_style

        # Basis-Styles je nach Template
        base_styles = {
            'minimal': f'padding: 16px; border-left: 4px solid {color};',
            'card': f'padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border: 1px solid #e5e7eb;',
            'gradient': f'padding: 20px; border-radius: 12px; background: linear-gradient(135deg, {color}, {color}dd); color: white;',
            'banner': f'padding: 16px 24px; border-radius: 8px; background: {color}15; border: 1px solid {color}40;',
            'highlight': f'padding: 20px; border-radius: 12px; background: {color}10; border: 2px solid {color};',
            'dark': 'padding: 20px; border-radius: 12px; background: #1f2937; color: white;',
        }

        container_style = base_styles.get(style, base_styles['card'])
        text_color = 'white' if style in ['gradient', 'dark'] else '#1f2937'
        desc_color = 'rgba(255,255,255,0.9)' if style in ['gradient', 'dark'] else '#6b7280'
        btn_bg = 'white' if style in ['gradient', 'dark'] else color
        btn_color = color if style in ['gradient', 'dark'] else 'white'

        image_html = ''
        if obj.image:
            image_html = f'<img src="{obj.image.url}" style="max-width: 120px; max-height: 80px; object-fit: cover; border-radius: 8px; margin-right: 16px;" />'

        return format_html(
            '''
            <div style="max-width: 500px; {}">
                <div style="display: flex; align-items: center;">
                    {}
                    <div style="flex: 1;">
                        <h4 style="margin: 0 0 8px 0; color: {}; font-size: 16px;">{}</h4>
                        <p style="margin: 0 0 12px 0; color: {}; font-size: 14px;">{}</p>
                        <span style="display: inline-block; background: {}; color: {}; padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 500;">{}</span>
                    </div>
                </div>
            </div>
            ''',
            container_style,
            image_html,
            text_color, obj.title,
            desc_color, obj.description or 'Keine Beschreibung',
            btn_bg, btn_color, obj.button_text
        )
    preview_large.short_description = 'Vorschau'

    class Media:
        css = {
            'all': ['admin/css/forms.css']
        }


# Import Auto-Campaign Admin Classes (legacy)
from .admin_auto import *

# Import App-Campaign Admin Classes (legacy)
from .admin_app import *
