from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, AmpelCategory, CategoryKeyword, AppPermission


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