from django.contrib import admin
from .models import VideoProject, Character, Product, StillImage, GeneratedFrame, Scene


class CharacterInline(admin.TabularInline):
    model = Character
    extra = 0
    max_num = 3


class ProductInline(admin.StackedInline):
    model = Product
    max_num = 1


class StillImageInline(admin.StackedInline):
    model = StillImage
    max_num = 1


class SceneInline(admin.TabularInline):
    model = Scene
    extra = 0


@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'created_at', 'updated_at']
    list_filter = ['created_at']
    search_fields = ['name']
    inlines = [CharacterInline, ProductInline, StillImageInline, SceneInline]


@admin.register(GeneratedFrame)
class GeneratedFrameAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'project', 'frame_type', 'status', 'created_at']
    list_filter = ['frame_type', 'status']


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'project', 'status', 'duration', 'created_at']
    list_filter = ['status']
