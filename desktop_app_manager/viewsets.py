"""
Desktop App Manager ViewSets
REST API Views fuer App-Verwaltung
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Sum, Q

from .models import DesktopApp, AppVersion, DownloadLog
from .serializers import (
    DesktopAppListSerializer, DesktopAppDetailSerializer,
    AppVersionListSerializer, AppVersionDetailSerializer,
    DownloadLogSerializer, UpdateCheckSerializer,
)
from .permissions import IsAppOwnerOrReadOnly, IsVersionOwnerOrReadOnly


class DesktopAppViewSet(viewsets.ModelViewSet):
    """ViewSet fuer Desktop App Management"""

    permission_classes = [IsAppOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'app_identifier', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return DesktopApp.objects.filter(
                Q(created_by=user) | Q(is_public=True)
            ).distinct().select_related('created_by').prefetch_related('versions')
        else:
            return DesktopApp.objects.filter(
                is_public=True
            ).select_related('created_by').prefetch_related('versions')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DesktopAppDetailSerializer
        return DesktopAppListSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        app = self.get_object()
        versions = app.versions.all()
        stats = {
            'total_versions': versions.count(),
            'active_versions': versions.filter(is_active=True).count(),
            'total_downloads': app.total_downloads,
            'downloads_by_channel': {},
            'downloads_by_version': []
        }

        for channel in ['alpha', 'beta', 'production']:
            channel_downloads = versions.filter(
                channel=channel
            ).aggregate(total=Sum('download_count'))['total'] or 0
            stats['downloads_by_channel'][channel] = channel_downloads

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
    """ViewSet fuer App Version Management"""

    permission_classes = [IsVersionOwnerOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version_code', 'uploaded_at']
    ordering = ['-version_code']

    def get_queryset(self):
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
        if self.action == 'retrieve':
            return AppVersionDetailSerializer
        return AppVersionListSerializer

    @action(detail=True, methods=['post'])
    def mark_as_current(self, request, pk=None):
        version = self.get_object()
        AppVersion.objects.filter(
            app=version.app,
            channel=version.channel
        ).update(is_current_for_channel=False)

        version.is_current_for_channel = True
        version.save()

        return Response(
            {'message': f'Version {version.version_name} marked as current for {version.channel} channel'},
            status=status.HTTP_200_OK
        )


class PublicAPIViewSet(viewsets.ViewSet):
    """
    Public API fuer Desktop-Clients
    Kein Authentication erforderlich
    """

    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='check-update')
    def check_update(self, request):
        """
        Check fuer verfuegbare Updates
        POST /api/desktop-apps/public/check-update/

        Body: {
            "app_identifier": "pdf-marker",
            "current_version_code": 1,
            "channel": "production",
            "windows_version": "10"
        }
        """
        serializer = UpdateCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        app_identifier = serializer.validated_data['app_identifier']
        current_version_code = serializer.validated_data['current_version_code']
        channel = serializer.validated_data.get('channel', 'production')

        try:
            app = DesktopApp.objects.get(app_identifier=app_identifier, is_public=True)

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

            update_available = latest_version.version_code > current_version_code

            latest_version_serializer = AppVersionDetailSerializer(
                latest_version if update_available else None,
                context={'request': request}
            )

            return Response({
                'update_available': update_available,
                'latest_version': latest_version_serializer.data if update_available else None,
                'message': 'Update available' if update_available else 'App is up to date'
            })

        except DesktopApp.DoesNotExist:
            return Response(
                {'error': 'App not found or not public'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], url_path='list-apps')
    def list_apps(self, request):
        """Liste aller oeffentlichen Apps"""
        apps = DesktopApp.objects.filter(is_public=True).select_related('created_by')
        serializer = DesktopAppListSerializer(
            apps,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class DownloadLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet fuer Download-Logs (Read-Only)"""

    serializer_class = DownloadLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['downloaded_at']
    ordering = ['-downloaded_at']

    def get_queryset(self):
        user = self.request.user
        return DownloadLog.objects.filter(
            app_version__app__created_by=user
        ).select_related('app_version', 'app_version__app')
