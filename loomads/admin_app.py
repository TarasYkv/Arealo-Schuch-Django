from django.contrib import admin
from django.utils.html import format_html
from .models import AppCampaign, AppAdvertisement


# ========== APP CAMPAIGN ADMIN ==========

class AppAdvertisementInline(admin.TabularInline):
    model = AppAdvertisement
    extra = 1
    fields = ['name', 'ad_type', 'weight', 'is_active', 'impressions_count', 'clicks_count']
    readonly_fields = ['impressions_count', 'clicks_count']


@admin.register(AppCampaign)
class AppCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'app_target_display', 'status_badge', 'priority',
        'start_date', 'end_date', 'target_zones_count',
        'ads_count', 'impressions_count', 'clicks_count', 'ctr_display'
    ]
    list_filter = ['app_target', 'status', 'priority', 'start_date', 'end_date', 'created_by']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'target_zones_display']
    date_hierarchy = 'start_date'
    inlines = [AppAdvertisementInline]

    fieldsets = (
        ('Grundinformationen', {
            'fields': ('name', 'description', 'app_target', 'status', 'priority', 'created_by')
        }),
        ('Zeitplanung', {
            'fields': ('start_date', 'end_date')
        }),
        ('Zone-Zuordnung', {
            'fields': ('auto_include_new_zones', 'exclude_zone_types', 'target_zones_display'),
            'description': 'Automatische Zuordnung zu allen Zonen der gewählten App'
        }),
        ('Performance-Einstellungen', {
            'fields': ('weight_multiplier',),
            'classes': ('collapse',)
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

    def app_target_display(self, obj):
        colors = {
            'loomline': 'primary',
            'fileshare': 'danger',
            'streamrec': 'secondary',
            'promptpro': 'info',
            'blog': 'success',
            'videos': 'info',
            'chat': 'warning',
            'global': 'dark',
            'shopify': 'success',
            'dashboard': 'success',
        }
        color = colors.get(obj.app_target, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_app_target_display()
        )
    app_target_display.short_description = 'Ziel-App'

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

    def target_zones_count(self, obj):
        count = obj.get_target_zones_count()
        return format_html(
            '<span class="badge bg-info">{} Zonen</span>',
            count
        )
    target_zones_count.short_description = 'Ziel-Zonen'

    def target_zones_display(self, obj):
        zones = obj.get_target_zones()
        if not zones:
            return format_html('<em>Keine Zonen gefunden für App "{}"</em>', obj.get_app_target_display())

        zone_list = []
        for zone in zones[:10]:  # Limit to first 10 zones
            zone_list.append(f"• {zone.name} ({zone.code})")

        if len(zones) > 10:
            zone_list.append(f"... und {len(zones) - 10} weitere")

        return format_html('<pre>{}</pre>', '\n'.join(zone_list))
    target_zones_display.short_description = 'Automatisch zugeordnete Zonen'

    def ads_count(self, obj):
        count = obj.app_advertisements.count()
        return format_html('<span class="badge bg-primary">{}</span>', count)
    ads_count.short_description = 'Anzeigen'

    def impressions_count(self, obj):
        count = obj.get_total_impressions()
        return format_html('<span class="badge bg-info">{}</span>', f'{count:,}')
    impressions_count.short_description = 'Impressions'

    def clicks_count(self, obj):
        count = obj.get_total_clicks()
        return format_html('<span class="badge bg-success">{}</span>', f'{count:,}')
    clicks_count.short_description = 'Klicks'

    def ctr_display(self, obj):
        ctr = obj.get_ctr()
        color = 'success' if ctr > 2.0 else 'warning' if ctr > 1.0 else 'danger'
        return format_html('<span class="badge bg-{}">{:.2f}%</span>', color, ctr)
    ctr_display.short_description = 'CTR'

    actions = ['sync_zones_action']

    def sync_zones_action(self, request, queryset):
        for campaign in queryset:
            campaign.sync_zones()
        self.message_user(request, f'{queryset.count()} App-Kampagnen wurden mit ihren Zonen synchronisiert.')
    sync_zones_action.short_description = 'Zonen-Synchronisation durchführen'


@admin.register(AppAdvertisement)
class AppAdvertisementAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'app_campaign', 'app_target_display', 'ad_type',
        'effective_weight_display', 'device_targeting', 'is_active',
        'zones_count', 'impressions_count', 'clicks_count', 'ctr_display'
    ]
    list_filter = [
        'app_campaign__app_target', 'ad_type', 'device_targeting',
        'is_active', 'app_campaign__status'
    ]
    search_fields = ['name', 'description', 'title', 'app_campaign__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'zones_display', 'effective_weight_display']
    filter_horizontal = ['zones']

    fieldsets = (
        ('Grundinformationen', {
            'fields': ('name', 'description', 'app_campaign', 'ad_type', 'is_active')
        }),
        ('Anzeigeninhalt', {
            'fields': ('title', 'description_text', 'html_content', 'image', 'video_url', 'link_url', 'link_text')
        }),
        ('Targeting & Gewichtung', {
            'fields': ('weight', 'effective_weight_display', 'device_targeting')
        }),
        ('Zone-Zuordnung', {
            'fields': ('zones', 'zones_display'),
            'description': 'Automatisch synchronisiert mit App-Kampagne'
        }),
        ('Performance-Daten', {
            'fields': ('impressions_count', 'clicks_count'),
            'classes': ('collapse',)
        }),
        ('Metadaten', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def app_target_display(self, obj):
        colors = {
            'loomline': 'primary',
            'fileshare': 'danger',
            'streamrec': 'secondary',
            'promptpro': 'info',
            'blog': 'success',
            'videos': 'info',
            'chat': 'warning',
            'global': 'dark',
            'shopify': 'success',
            'dashboard': 'success',
        }
        color = colors.get(obj.app_campaign.app_target, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.app_campaign.get_app_target_display()
        )
    app_target_display.short_description = 'App'

    def effective_weight_display(self, obj):
        return format_html(
            '<span class="badge bg-info">{:.1f}</span>',
            obj.effective_weight
        )
    effective_weight_display.short_description = 'Effektive Gewichtung'

    def zones_count(self, obj):
        count = obj.zones.count()
        return format_html('<span class="badge bg-secondary">{}</span>', count)
    zones_count.short_description = 'Zonen'

    def zones_display(self, obj):
        zones = obj.zones.all()
        if not zones:
            return format_html('<em>Keine Zonen zugeordnet</em>')

        zone_list = []
        for zone in zones[:10]:  # Limit to first 10 zones
            zone_list.append(f"• {zone.name} ({zone.code})")

        if len(zones) > 10:
            zone_list.append(f"... und {len(zones) - 10} weitere")

        return format_html('<pre>{}</pre>', '\n'.join(zone_list))
    zones_display.short_description = 'Zugeordnete Zonen'

    def impressions_count(self, obj):
        return format_html('<span class="badge bg-info">{}</span>', f'{obj.impressions_count:,}')
    impressions_count.short_description = 'Impressions'

    def clicks_count(self, obj):
        return format_html('<span class="badge bg-success">{}</span>', f'{obj.clicks_count:,}')
    clicks_count.short_description = 'Klicks'

    def ctr_display(self, obj):
        ctr = obj.get_ctr()
        color = 'success' if ctr > 2.0 else 'warning' if ctr > 1.0 else 'danger'
        return format_html('<span class="badge bg-{}">{:.2f}%</span>', color, ctr)
    ctr_display.short_description = 'CTR'

    actions = ['sync_with_app_zones_action']

    def sync_with_app_zones_action(self, request, queryset):
        for ad in queryset:
            ad.sync_with_app_zones()
        self.message_user(request, f'{queryset.count()} App-Anzeigen wurden mit ihren App-Zonen synchronisiert.')
    sync_with_app_zones_action.short_description = 'Mit App-Zonen synchronisieren'