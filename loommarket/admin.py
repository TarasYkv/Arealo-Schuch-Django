from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Business, BusinessImage, MockupTemplate,
    MarketingCampaign, SocialMediaCaption, SocialMediaPost
)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'instagram_username', 'user', 'status', 'image_count', 'created_at']
    list_filter = ['status', 'created_at', 'user']
    search_fields = ['name', 'instagram_username', 'website']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def image_count(self, obj):
        return obj.images.count()
    image_count.short_description = 'Bilder'


class BusinessImageInline(admin.TabularInline):
    model = BusinessImage
    extra = 0
    readonly_fields = ['image_preview', 'created_at']
    fields = ['image_preview', 'image', 'is_logo', 'order', 'source_url']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 80px; max-height: 80px;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Vorschau'


@admin.register(BusinessImage)
class BusinessImageAdmin(admin.ModelAdmin):
    list_display = ['business', 'image_preview', 'is_logo', 'order', 'created_at']
    list_filter = ['is_logo', 'created_at', 'business']
    ordering = ['business', 'order']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 60px; max-height: 60px;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Bild'


@admin.register(MockupTemplate)
class MockupTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'image_preview', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']

    def image_preview(self, obj):
        if obj.product_image_blank:
            return format_html('<img src="{}" style="max-width: 80px; max-height: 80px;" />', obj.product_image_blank.url)
        return '-'
    image_preview.short_description = 'Produktbild'


class SocialMediaCaptionInline(admin.TabularInline):
    model = SocialMediaCaption
    extra = 0
    readonly_fields = ['created_at']
    fields = ['platform', 'title', 'caption_text', 'hashtags']


class SocialMediaPostInline(admin.TabularInline):
    model = SocialMediaPost
    extra = 0
    readonly_fields = ['created_at', 'published_at']
    fields = ['platform', 'post_type', 'status', 'external_post_id', 'created_at']


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ['campaign_name', 'business', 'template', 'status', 'has_mockup', 'post_count', 'created_at']
    list_filter = ['status', 'created_at', 'template']
    search_fields = ['name', 'business__name', 'business__instagram_username']

    def campaign_name(self, obj):
        return obj.name or f"Kampagne {obj.pk}"
    campaign_name.short_description = 'Name'
    readonly_fields = ['created_at', 'updated_at']
    inlines = [SocialMediaCaptionInline, SocialMediaPostInline]

    def has_mockup(self, obj):
        return bool(obj.mockup_image)
    has_mockup.boolean = True
    has_mockup.short_description = 'Mockup'

    def post_count(self, obj):
        return obj.posts.count()
    post_count.short_description = 'Posts'


@admin.register(SocialMediaCaption)
class SocialMediaCaptionAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'platform', 'title', 'created_at']
    list_filter = ['platform', 'created_at']
    search_fields = ['title', 'caption_text', 'campaign__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SocialMediaPost)
class SocialMediaPostAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'platform', 'post_type', 'status', 'published_at', 'created_at']
    list_filter = ['platform', 'post_type', 'status', 'created_at']
    search_fields = ['campaign__name', 'external_post_id']
    readonly_fields = ['created_at', 'published_at']
