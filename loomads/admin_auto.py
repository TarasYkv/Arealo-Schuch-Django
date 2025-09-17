"""
Admin-Interface für automatische LoomAds Kampagnen
"""
from django.contrib import admin
from . import models


# Auto-Campaign Admin Classes

class AutoAdvertisementInline(admin.TabularInline):
    model = models.AutoAdvertisement
    extra = 0
    readonly_fields = ('id', 'target_zone', 'performance_score', 'created_at')
    fields = ('name', 'target_zone', 'generation_strategy', 'is_active', 'performance_score')
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(models.AutoCampaignFormat)
class AutoCampaignFormatAdmin(admin.ModelAdmin):
    list_display = ('name', 'format_type', 'zone_count_display', 'grouping_strategy', 'is_active', 'priority')
    list_filter = ('format_type', 'grouping_strategy', 'is_active')
    search_fields = ('name', 'description')
    ordering = ['-priority', 'name']
    
    fieldsets = (
        ('Basis-Informationen', {
            'fields': ('name', 'format_type', 'description', 'is_active', 'priority')
        }),
        ('Format-Spezifikationen', {
            'fields': ('target_zone_types', 'target_dimensions', 'excluded_zones'),
            'description': 'Definiert welche Zonen zu diesem Format gehören'
        }),
        ('Automatische Gruppierung', {
            'fields': ('grouping_strategy', 'auto_assign_similar_zones'),
        }),
    )
    
    def zone_count_display(self, obj):
        count = obj.get_zone_count()
        return f"{count} Zonen"
    zone_count_display.short_description = 'Passende Zonen'
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ('format_type',)
        return self.readonly_fields
    
    actions = ['create_sample_formats']
    
    def create_sample_formats(self, request, queryset):
        """Erstellt Beispiel-Formate basierend auf existierenden Zonen"""
        created_formats = []
        
        # Banner 728x90 Format
        banner_format, created = models.AutoCampaignFormat.objects.get_or_create(
            format_type='banner_728x90',
            defaults={
                'name': 'Standard Banner 728x90',
                'description': 'Alle Header- und Footer-Banner im 728x90 Format',
                'target_zone_types': ['header', 'footer'],
                'target_dimensions': ['728x90'],
                'grouping_strategy': 'by_type_and_dimensions',
                'priority': 10
            }
        )
        if created:
            created_formats.append(banner_format.name)
        
        # Sidebar 300x250 Format
        sidebar_format, created = models.AutoCampaignFormat.objects.get_or_create(
            format_type='sidebar_300x250',
            defaults={
                'name': 'Standard Sidebar 300x250',
                'description': 'Alle Sidebar-Bereiche im 300x250 Format',
                'target_zone_types': ['sidebar'],
                'target_dimensions': ['300x250'],
                'grouping_strategy': 'by_type_and_dimensions',
                'priority': 8
            }
        )
        if created:
            created_formats.append(sidebar_format.name)
        
        # Content Card Format
        content_format, created = models.AutoCampaignFormat.objects.get_or_create(
            format_type='content_card_350x200',
            defaults={
                'name': 'Content Cards 350x200',
                'description': 'Alle Content Card Bereiche im 350x200 Format',
                'target_zone_types': ['content_card'],
                'target_dimensions': ['350x200', '350x250'],
                'grouping_strategy': 'by_type_and_dimensions',
                'priority': 6
            }
        )
        if created:
            created_formats.append(content_format.name)
        
        if created_formats:
            self.message_user(request, f"Erfolgreich erstellt: {', '.join(created_formats)}")
        else:
            self.message_user(request, "Alle Standard-Formate existieren bereits.")
    
    create_sample_formats.short_description = "Standard-Formate erstellen"


@admin.register(models.AutoCampaign)
class AutoCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'target_format', 'status', 'performance_score_display', 'auto_ads_count', 'created_at')
    list_filter = ('status', 'target_format__format_type', 'content_strategy', 'auto_optimize_performance')
    search_fields = ('name', 'description', 'target_format__name')
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    inlines = [AutoAdvertisementInline]
    
    fieldsets = (
        ('Kampagnen-Informationen', {
            'fields': ('name', 'description', 'target_format', 'status')
        }),
        ('Zeitraum', {
            'fields': ('start_date', 'end_date')
        }),
        ('Automatische Einstellungen', {
            'fields': ('content_strategy', 'auto_optimize_performance', 'auto_pause_low_performers', 'performance_threshold_ctr'),
            'classes': ['collapse']
        }),
        ('Budget & Limits', {
            'fields': ('daily_impression_limit', 'total_impression_limit'),
            'classes': ['collapse']
        }),
        ('Performance-Tracking', {
            'fields': ('performance_score', 'auto_created_ads_count', 'last_optimization_run'),
            'classes': ['collapse']
        }),
    )
    
    readonly_fields = ('performance_score', 'auto_created_ads_count', 'last_optimization_run')
    
    def performance_score_display(self, obj):
        score = obj.performance_score
        if score == 0:
            return "—"
        return f"{score:.1f}%"
    performance_score_display.short_description = 'Performance'
    
    def auto_ads_count(self, obj):
        return obj.auto_created_ads_count
    auto_ads_count.short_description = 'Auto-Ads'
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['run_optimization', 'create_auto_ads', 'activate_campaigns', 'pause_campaigns']
    
    def run_optimization(self, request, queryset):
        """Führt Performance-Optimierung für ausgewählte Kampagnen durch"""
        results = []
        for campaign in queryset:
            if campaign.status == 'active':
                optimization_result = campaign.optimize_performance()
                results.append(f"{campaign.name}: Score {optimization_result['total_score']:.1f}%")
        
        if results:
            self.message_user(request, f"Optimierung durchgeführt: {'; '.join(results)}")
        else:
            self.message_user(request, "Keine aktiven Kampagnen zum Optimieren gefunden.")
    
    run_optimization.short_description = "Performance-Optimierung durchführen"
    
    def create_auto_ads(self, request, queryset):
        """Erstellt automatisch Ads für die ausgewählten Kampagnen"""
        # Hier würde eine Seite zur Auswahl des Base-Creative geöffnet
        self.message_user(request, "Auto-Ad Erstellung - Bitte Base-Creative auswählen (noch nicht implementiert)")
    
    create_auto_ads.short_description = "Auto-Ads erstellen"
    
    def activate_campaigns(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f"{updated} Kampagnen aktiviert.")
    
    activate_campaigns.short_description = "Kampagnen aktivieren"
    
    def pause_campaigns(self, request, queryset):
        updated = queryset.update(status='paused')
        self.message_user(request, f"{updated} Kampagnen pausiert.")
    
    pause_campaigns.short_description = "Kampagnen pausieren"


@admin.register(models.AutoAdvertisement)
class AutoAdvertisementAdmin(admin.ModelAdmin):
    list_display = ('name', 'auto_campaign', 'target_zone', 'generation_strategy', 'performance_score_display', 'is_active')
    list_filter = ('generation_strategy', 'is_active', 'auto_campaign__status')
    search_fields = ('name', 'auto_campaign__name', 'target_zone__code')
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basis-Informationen', {
            'fields': ('name', 'auto_campaign', 'target_zone', 'is_active')
        }),
        ('Creative-Daten', {
            'fields': ('base_creative', 'generation_strategy', 'generation_metadata'),
        }),
        ('Performance', {
            'fields': ('performance_score', 'advertisement'),
            'classes': ['collapse']
        }),
    )
    
    readonly_fields = ('performance_score', 'advertisement')
    
    def performance_score_display(self, obj):
        score = obj.performance_score
        if score == 0:
            return "—"
        return f"{score:.1f}%"
    performance_score_display.short_description = 'Performance'
    
    actions = ['generate_advertisements', 'update_performance_scores']
    
    def generate_advertisements(self, request, queryset):
        """Generiert die tatsächlichen Advertisements für Auto-Ads"""
        generated = 0
        for auto_ad in queryset:
            if not auto_ad.advertisement:
                auto_ad.generate_advertisement()
                generated += 1
        
        self.message_user(request, f"{generated} Advertisements generiert.")
    
    generate_advertisements.short_description = "Advertisements generieren"
    
    def update_performance_scores(self, request, queryset):
        """Aktualisiert Performance-Scores"""
        updated = 0
        for auto_ad in queryset:
            auto_ad.update_performance_score()
            updated += 1
        
        self.message_user(request, f"{updated} Performance-Scores aktualisiert.")
    
    update_performance_scores.short_description = "Performance-Scores aktualisieren"