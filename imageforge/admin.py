from django.contrib import admin
from django.utils.html import format_html
from .models import Character, CharacterImage, ImageGeneration, StylePreset, ProductMockup


class CharacterImageInline(admin.TabularInline):
    model = CharacterImage
    extra = 1
    fields = ['image', 'is_primary', 'upload_order']


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'image_count', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'description', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [CharacterImageInline]

    def image_count(self, obj):
        return obj.images.count()
    image_count.short_description = 'Bilder'


@admin.register(ImageGeneration)
class ImageGenerationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'generation_mode', 'ai_model', 'is_successful', 'is_favorite', 'created_at']
    list_filter = ['generation_mode', 'ai_model', 'is_favorite', 'created_at']
    search_fields = ['background_prompt', 'user__username']
    readonly_fields = ['created_at', 'generation_time', 'generation_prompt']
    list_select_related = ['user', 'character']

    fieldsets = [
        ('Allgemein', {
            'fields': ['user', 'generation_mode', 'background_prompt', 'character']
        }),
        ('Einstellungen', {
            'fields': ['aspect_ratio', 'lighting_style', 'perspective', 'style_preset',
                       'shadow_type', 'color_mood', 'quality', 'ai_model']
        }),
        ('Bilder', {
            'fields': ['product_image', 'generated_image']
        }),
        ('Meta', {
            'fields': ['is_favorite', 'created_at', 'generation_time', 'generation_prompt', 'error_message'],
            'classes': ['collapse']
        }),
    ]

    def is_successful(self, obj):
        if obj.generated_image:
            return format_html('<span style="color: green;">&#10004;</span>')
        return format_html('<span style="color: red;">&#10008;</span>')
    is_successful.short_description = 'Erfolgreich'


@admin.register(StylePreset)
class StylePresetAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_default', 'created_at']
    list_filter = ['is_default', 'created_at']
    search_fields = ['name', 'user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProductMockup)
class ProductMockupAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'text_content', 'text_application_type', 'has_mockup_image', 'is_favorite', 'created_at']
    list_filter = ['text_application_type', 'ai_model', 'is_favorite', 'created_at']
    search_fields = ['name', 'text_content', 'user__username']
    readonly_fields = ['created_at', 'generation_time', 'generation_prompt']
    list_select_related = ['user']

    fieldsets = [
        ('Allgemein', {
            'fields': ['user', 'name', 'text_content']
        }),
        ('Text-Einstellungen', {
            'fields': ['text_application_type', 'text_position', 'font_style', 'text_size', 'text_color_hint']
        }),
        ('Bilder', {
            'fields': ['product_image', 'style_reference_image', 'mockup_image']
        }),
        ('Meta', {
            'fields': ['ai_model', 'is_favorite', 'created_at', 'generation_time', 'generation_prompt'],
            'classes': ['collapse']
        }),
    ]

    def has_mockup_image(self, obj):
        if obj.mockup_image:
            return format_html('<span style="color: green;">&#10004;</span>')
        return format_html('<span style="color: red;">&#10008;</span>')
    has_mockup_image.short_description = 'Mockup'
