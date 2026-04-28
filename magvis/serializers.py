from rest_framework import serializers

from .models import (
    MagvisBlog,
    MagvisImageAsset,
    MagvisProject,
    MagvisReportConfig,
    MagvisSettings,
    MagvisTopicQueue,
)


class MagvisSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MagvisSettings
        exclude = ['user']


class MagvisReportConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = MagvisReportConfig
        exclude = ['user']


class MagvisTopicQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = MagvisTopicQueue
        exclude = ['user']
        read_only_fields = ['used_at', 'used_by_project', 'created_at']


class MagvisImageAssetSerializer(serializers.ModelSerializer):
    effective_path = serializers.CharField(read_only=True)

    class Meta:
        model = MagvisImageAsset
        fields = '__all__'
        read_only_fields = ['project', 'created_at', 'updated_at',
                            'src_path', 'src_url', 'source', 'source_ref']


class MagvisBlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MagvisBlog
        fields = '__all__'
        read_only_fields = ['project', 'created_at', 'updated_at']


class MagvisProjectSerializer(serializers.ModelSerializer):
    blog = MagvisBlogSerializer(read_only=True)
    image_assets = MagvisImageAssetSerializer(many=True, read_only=True)
    next_stage = serializers.SerializerMethodField()

    class Meta:
        model = MagvisProject
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at', 'celery_eta_task_id',
                            'task_ids', 'stage_logs', 'cost_total',
                            'vidgen_project', 'posted_video',
                            'youtube_url', 'youtube_video_id',
                            'ploom_session_1', 'ploom_session_2',
                            'product_1', 'product_2',
                            'blog', 'image_assets', 'next_stage']

    def get_next_stage(self, obj):
        return obj.next_stage_slug()
