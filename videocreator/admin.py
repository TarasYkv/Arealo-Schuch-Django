from django.contrib import admin
from .models import VideoProject, VideoAsset, GeneratedImage, VideoScene


@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'user_id', 'created_at', 'updated_at']
    search_fields = ['name', 'user_id']


@admin.register(VideoAsset)
class VideoAssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'project', 'created_at']
    list_filter = ['type']


@admin.register(GeneratedImage)
class GeneratedImageAdmin(admin.ModelAdmin):
    list_display = ['prompt', 'model', 'status', 'created_at']
    list_filter = ['status', 'model']


@admin.register(VideoScene)
class VideoSceneAdmin(admin.ModelAdmin):
    list_display = ['project', 'order', 'video_model', 'video_status']
    list_filter = ['video_status', 'video_model']
