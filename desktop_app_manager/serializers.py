"""
Desktop App Manager Serializers
REST API Serialization fuer Desktop Apps und Versionen
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DesktopApp, AppVersion, DownloadLog

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']
        read_only_fields = ['id']


class AppVersionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer fuer Version-Listen"""
    download_count = serializers.IntegerField(read_only=True)
    file_size_mb = serializers.FloatField(read_only=True)

    class Meta:
        model = AppVersion
        fields = [
            'id', 'version_name', 'version_code', 'channel',
            'file_size', 'file_size_mb', 'download_count',
            'is_active', 'is_current_for_channel',
            'min_windows_version', 'uploaded_at'
        ]
        read_only_fields = ['id', 'file_size', 'uploaded_at']


class AppVersionDetailSerializer(serializers.ModelSerializer):
    """Detailed version serializer mit Download-URL"""
    app_name = serializers.CharField(source='app.name', read_only=True)
    app_identifier = serializers.CharField(source='app.app_identifier', read_only=True)
    download_url = serializers.SerializerMethodField()
    file_size_mb = serializers.FloatField(read_only=True)

    class Meta:
        model = AppVersion
        fields = [
            'id', 'app', 'app_name', 'app_identifier',
            'version_name', 'version_code', 'release_notes',
            'channel', 'min_windows_version',
            'exe_file', 'file_size', 'file_size_mb', 'file_hash',
            'download_count', 'download_url',
            'is_active', 'is_current_for_channel',
            'uploaded_at', 'updated_at'
        ]
        read_only_fields = ['id', 'file_size', 'file_hash', 'download_count', 'uploaded_at', 'updated_at']

    def get_download_url(self, obj):
        """Generiere Download-URL"""
        request = self.context.get('request')
        if request:
            from django.urls import reverse
            return request.build_absolute_uri(
                reverse('desktop_app_manager:download-exe', kwargs={'version_id': str(obj.id)})
            )
        return None


class DesktopAppListSerializer(serializers.ModelSerializer):
    """Lightweight serializer fuer App-Listen"""
    created_by = UserBasicSerializer(read_only=True)
    latest_version = AppVersionListSerializer(read_only=True)
    total_downloads = serializers.IntegerField(read_only=True)
    version_count = serializers.SerializerMethodField()

    class Meta:
        model = DesktopApp
        fields = [
            'id', 'name', 'app_identifier', 'description', 'icon',
            'created_by', 'is_public', 'latest_version',
            'total_downloads', 'version_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_version_count(self, obj):
        return obj.versions.filter(is_active=True).count()


class DesktopAppDetailSerializer(serializers.ModelSerializer):
    """Detailed app serializer mit allen Versionen"""
    created_by = UserBasicSerializer(read_only=True)
    versions = AppVersionListSerializer(many=True, read_only=True)
    total_downloads = serializers.IntegerField(read_only=True)

    class Meta:
        model = DesktopApp
        fields = [
            'id', 'name', 'app_identifier', 'description', 'icon',
            'created_by', 'is_public', 'versions', 'total_downloads',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class DownloadLogSerializer(serializers.ModelSerializer):
    """Serializer fuer Download-Statistiken"""
    app_version_name = serializers.CharField(
        source='app_version.version_name',
        read_only=True
    )

    class Meta:
        model = DownloadLog
        fields = [
            'id', 'app_version', 'app_version_name',
            'downloaded_at', 'ip_address', 'user_agent',
            'windows_version',
            'download_completed'
        ]
        read_only_fields = ['id', 'downloaded_at']


class UpdateCheckSerializer(serializers.Serializer):
    """Serializer fuer Update-Check Request"""
    app_identifier = serializers.CharField(required=True)
    current_version_code = serializers.IntegerField(required=True)
    channel = serializers.ChoiceField(
        choices=['alpha', 'beta', 'production'],
        default='production',
        required=False
    )
    windows_version = serializers.CharField(required=False, allow_blank=True)


class UpdateCheckResponseSerializer(serializers.Serializer):
    """Serializer fuer Update-Check Response"""
    update_available = serializers.BooleanField()
    latest_version = AppVersionDetailSerializer(allow_null=True)
    message = serializers.CharField(required=False)
