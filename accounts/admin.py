from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import CustomUser, AmpelCategory, CategoryKeyword, AppPermission, FeatureAccess


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Benutzerdefinierte Einstellungen', {'fields': ('use_custom_categories', 'enable_ai_keyword_expansion')}),
        ('App-Berechtigungen', {'fields': ('can_manage_app_permissions',)}),
    )
    list_display = UserAdmin.list_display + ('use_custom_categories', 'enable_ai_keyword_expansion', 'can_manage_app_permissions')


class CategoryKeywordInline(admin.TabularInline):
    model = CategoryKeyword
    extra = 1


@admin.register(AmpelCategory)
class AmpelCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'user')
    search_fields = ('name', 'description', 'user__username')
    inlines = [CategoryKeywordInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)


@admin.register(CategoryKeyword)
class CategoryKeywordAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'category', 'weight', 'created_at')
    list_filter = ('weight', 'created_at', 'category__user')
    search_fields = ('keyword', 'category__name', 'category__user__username')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(category__user=request.user)


@admin.register(AppPermission)
class AppPermissionAdmin(admin.ModelAdmin):
    list_display = ('get_app_display', 'access_level', 'is_active', 'updated_at')
    list_filter = ('access_level', 'is_active', 'app_name')
    search_fields = ('app_name',)
    filter_horizontal = ('selected_users',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('app_name', 'access_level', 'is_active')
        }),
        ('Erweiterte Optionen', {
            'fields': ('hide_in_frontend', 'superuser_bypass'),
            'description': 'Zusätzliche Steuerungsoptionen für App-Sichtbarkeit und Superuser-Zugriff'
        }),
        ('Ausgewählte Nutzer', {
            'fields': ('selected_users',),
            'description': 'Nur relevant wenn Zugriffsebene "Ausgewählte Nutzer" ist'
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_app_display(self, obj):
        return obj.get_app_name_display()
    get_app_display.short_description = 'App/Funktion'
    get_app_display.admin_order_field = 'app_name'


@admin.register(FeatureAccess)
class FeatureAccessAdmin(admin.ModelAdmin):
    list_display = ('get_app_display', 'subscription_required', 'is_active', 'show_upgrade_prompt', 'updated_at')
    list_filter = ('subscription_required', 'is_active', 'show_upgrade_prompt')
    search_fields = ('app_name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Grundeinstellungen', {
            'fields': ('app_name', 'subscription_required', 'is_active')
        }),
        ('Beschreibung & Nachrichten', {
            'fields': ('description', 'upgrade_message'),
            'description': 'Beschreibung der Funktion und benutzerdefinierte Upgrade-Nachricht'
        }),
        ('Anzeige-Optionen', {
            'fields': ('show_upgrade_prompt',),
            'description': 'Steuert ob Upgrade-Hinweise angezeigt werden'
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['setup_default_rules', 'activate_features', 'deactivate_features', 'set_free_access', 'set_founder_access']
    
    def get_app_display(self, obj):
        return obj.get_app_name_display()
    get_app_display.short_description = 'App/Feature'
    get_app_display.admin_order_field = 'app_name'
    
    def setup_default_rules(self, request, queryset):
        """Action um Standard-Zugriffsregeln zu erstellen"""
        FeatureAccess.setup_default_access_rules()
        self.message_user(request, "Standard-Zugriffsregeln wurden erstellt/aktualisiert.")
    setup_default_rules.short_description = "Standard-Zugriffsregeln erstellen"
    
    def activate_features(self, request, queryset):
        """Action um ausgewählte Features zu aktivieren"""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} Feature(s) wurden aktiviert.")
    activate_features.short_description = "Ausgewählte Features aktivieren"
    
    def deactivate_features(self, request, queryset):
        """Action um ausgewählte Features zu deaktivieren"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} Feature(s) wurden deaktiviert.")
    deactivate_features.short_description = "Ausgewählte Features deaktivieren"
    
    def set_free_access(self, request, queryset):
        """Action um Features kostenlos verfügbar zu machen"""
        count = queryset.update(subscription_required='free')
        self.message_user(request, f"{count} Feature(s) sind jetzt kostenlos verfügbar.")
    set_free_access.short_description = "Auf kostenlosen Zugang setzen"
    
    def set_founder_access(self, request, queryset):
        """Action um Features auf Founder Access zu setzen"""
        count = queryset.update(subscription_required='founder_access')
        self.message_user(request, f"{count} Feature(s) benötigen jetzt Founder's Early Access.")
    set_founder_access.short_description = "Auf Founder Access setzen"
    
    def changelist_view(self, request, extra_context=None):
        """Erweitert die Changelist-Ansicht um zusätzliche Informationen"""
        extra_context = extra_context or {}
        
        # Statistiken hinzufügen
        total_features = FeatureAccess.objects.count()
        free_features = FeatureAccess.objects.filter(subscription_required='free').count()
        founder_features = FeatureAccess.objects.filter(subscription_required='founder_access').count()
        paid_features = FeatureAccess.objects.filter(subscription_required='any_paid').count()
        
        extra_context['feature_stats'] = {
            'total': total_features,
            'free': free_features,
            'founder': founder_features,
            'paid': paid_features,
        }
        
        return super().changelist_view(request, extra_context=extra_context)