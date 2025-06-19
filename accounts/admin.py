from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, AmpelCategory, CategoryKeyword


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Benutzerdefinierte Einstellungen', {'fields': ('use_custom_categories', 'enable_ai_keyword_expansion')}),
    )
    list_display = UserAdmin.list_display + ('use_custom_categories', 'enable_ai_keyword_expansion')


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