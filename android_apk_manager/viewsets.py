"""
Android APK Manager ViewSets
REST API Views für App-Verwaltung
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404

from .models import AndroidApp, AppVersion, DownloadLog
from .serializers import (
    AndroidAppListSerializer, AndroidAppDetailSerializer,
    AppVersionListSerializer, AppVersionDetailSerializer,
    DownloadLogSerializer, UpdateCheckSerializer,
    UpdateCheckResponseSerializer
)
from .permissions import IsAppOwnerOrReadOnly, IsVersionOwnerOrReadOnly


class AndroidAppViewSet(viewsets.ModelViewSet):
    """
    ViewSet für Android App Management
    CRUD Operations für Apps
    """

    permission_classes = [IsAppOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'package_name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        """
        Zeige öffentliche Apps für alle
        Private Apps nur für Owner
        """
        user = self.request.user

        if user.is_authenticated:
            # Authenticated: Eigene Apps + öffentliche Apps
            return AndroidApp.objects.filter(
                Q(created_by=user) | Q(is_public=True)
            ).distinct().select_related('created_by').prefetch_related('versions')
        else:
            # Unauthenticated: Nur öffentliche Apps
            return AndroidApp.objects.filter(
                is_public=True
            ).select_related('created_by').prefetch_related('versions')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return AndroidAppDetailSerializer
        return AndroidAppListSerializer

    def perform_create(self, serializer):
        """Create app with current user als created_by"""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get app statistics"""
        app = self.get_object()

        versions = app.versions.all()
        stats = {
            'total_versions': versions.count(),
            'active_versions': versions.filter(is_active=True).count(),
            'total_downloads': app.total_downloads,
            'downloads_by_channel': {},
            'downloads_by_version': []
        }

        # Downloads per Channel
        for channel in ['alpha', 'beta', 'production']:
            channel_downloads = versions.filter(
                channel=channel
            ).aggregate(total=Sum('download_count'))['total'] or 0
            stats['downloads_by_channel'][channel] = channel_downloads

        # Top 5 Versionen nach Downloads
        top_versions = versions.order_by('-download_count')[:5]
        stats['downloads_by_version'] = [
            {
                'version_name': v.version_name,
                'version_code': v.version_code,
                'downloads': v.download_count
            }
            for v in top_versions
        ]

        return Response(stats)


class AppVersionViewSet(viewsets.ModelViewSet):
    """
    ViewSet für App Version Management
    CRUD Operations für Versionen
    """

    permission_classes = [IsVersionOwnerOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version_code', 'uploaded_at']
    ordering = ['-version_code']

    def get_queryset(self):
        """
        Zeige Versionen basierend auf App-Visibility
        """
        user = self.request.user

        if user.is_authenticated:
            return AppVersion.objects.filter(
                Q(app__created_by=user) | Q(app__is_public=True)
            ).distinct().select_related('app', 'app__created_by')
        else:
            return AppVersion.objects.filter(
                app__is_public=True
            ).select_related('app', 'app__created_by')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return AppVersionDetailSerializer
        return AppVersionListSerializer

    @action(detail=True, methods=['post'])
    def mark_as_current(self, request, pk=None):
        """
        Markiere Version als aktuelle Version für ihren Channel
        Entfernt Flag von anderen Versionen im selben Channel
        """
        version = self.get_object()

        # Entferne "current" Flag von allen anderen Versionen im selben Channel
        AppVersion.objects.filter(
            app=version.app,
            channel=version.channel
        ).update(is_current_for_channel=False)

        # Setze Flag für diese Version
        version.is_current_for_channel = True
        version.save()

        return Response(
            {'message': f'Version {version.version_name} marked as current for {version.channel} channel'},
            status=status.HTTP_200_OK
        )


class PublicAPIViewSet(viewsets.ViewSet):
    """
    Public API für Android-Clients (Flutter Apps)
    Kein Authentication erforderlich
    """

    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='check-update')
    def check_update(self, request):
        """
        Check für verfügbare Updates
        POST /api/android-apps/public/check-update/

        Body: {
            "package_name": "com.workloom.app",
            "current_version_code": 10,
            "channel": "production",  # optional
            "android_version": "11",  # optional
            "device_model": "Samsung Galaxy S21"  # optional
        }
        """
        serializer = UpdateCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        package_name = serializer.validated_data['package_name']
        current_version_code = serializer.validated_data['current_version_code']
        channel = serializer.validated_data.get('channel', 'production')

        try:
            # Finde App
            app = AndroidApp.objects.get(package_name=package_name, is_public=True)

            # Finde neueste Version für Channel
            latest_version = app.versions.filter(
                channel=channel,
                is_active=True
            ).order_by('-version_code').first()

            if not latest_version:
                return Response({
                    'update_available': False,
                    'latest_version': None,
                    'message': f'No active versions available for channel: {channel}'
                })

            # Check ob Update verfügbar
            update_available = latest_version.version_code > current_version_code

            # Serializer Context für URL-Generation
            latest_version_serializer = AppVersionDetailSerializer(
                latest_version if update_available else None,
                context={'request': request}
            )

            return Response({
                'update_available': update_available,
                'latest_version': latest_version_serializer.data if update_available else None,
                'message': 'Update available' if update_available else 'App is up to date'
            })

        except AndroidApp.DoesNotExist:
            return Response(
                {'error': 'App not found or not public'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], url_path='list-apps')
    def list_apps(self, request):
        """
        Liste aller öffentlichen Apps
        GET /api/android-apps/public/list-apps/
        """
        apps = AndroidApp.objects.filter(is_public=True).select_related('created_by')
        serializer = AndroidAppListSerializer(
            apps,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class DownloadLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet für Download-Logs (Read-Only)
    Nur für App-Owner sichtbar
    """

    serializer_class = DownloadLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['downloaded_at']
    ordering = ['-downloaded_at']

    def get_queryset(self):
        """Zeige nur Logs für eigene Apps"""
        user = self.request.user
        return DownloadLog.objects.filter(
            app_version__app__created_by=user
        ).select_related('app_version', 'app_version__app')
