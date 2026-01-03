from django.contrib import admin
from .models import LinkLoomPage, LinkLoomIcon, LinkLoomButton, LinkLoomClick


class LinkLoomIconInline(admin.TabularInline):
    model = LinkLoomIcon
    extra = 0
    ordering = ['sort_order']


class LinkLoomButtonInline(admin.TabularInline):
    model = LinkLoomButton
    extra = 0
    ordering = ['sort_order']
    readonly_fields = ['click_count', 'last_clicked']


@admin.register(LinkLoomPage)
class LinkLoomPageAdmin(admin.ModelAdmin):
    list_display = ['slug', 'user', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['slug', 'user__username', 'user__email', 'profile_description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [LinkLoomIconInline, LinkLoomButtonInline]
    fieldsets = (
        ('Basis', {
            'fields': ('user', 'slug', 'is_active')
        }),
        ('Profil', {
            'fields': ('profile_picture', 'profile_description')
        }),
        ('Design', {
            'fields': ('background_color', 'button_color', 'button_text_color', 'profile_text_color')
        }),
        ('Footer', {
            'fields': ('custom_impressum', 'show_affiliate_disclaimer', 'affiliate_disclaimer_text')
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LinkLoomIcon)
class LinkLoomIconAdmin(admin.ModelAdmin):
    list_display = ['platform', 'page', 'url', 'sort_order', 'is_active']
    list_filter = ['platform', 'is_active']
    search_fields = ['page__slug', 'url']


@admin.register(LinkLoomButton)
class LinkLoomButtonAdmin(admin.ModelAdmin):
    list_display = ['title', 'page', 'url', 'click_count', 'is_active']
    list_filter = ['is_active', 'page']
    search_fields = ['title', 'page__slug', 'url', 'description']
    readonly_fields = ['click_count', 'last_clicked']


@admin.register(LinkLoomClick)
class LinkLoomClickAdmin(admin.ModelAdmin):
    list_display = ['button', 'clicked_at', 'ip_address']
    list_filter = ['clicked_at']
    search_fields = ['button__title', 'button__page__slug']
    readonly_fields = ['button', 'clicked_at', 'ip_address', 'user_agent', 'referer']
    date_hierarchy = 'clicked_at'
