"""DRF ViewSets für Magvis (Agent-API)."""
from __future__ import annotations

from celery.result import AsyncResult
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import MagvisImageAsset, MagvisProject, MagvisTopicQueue
from .permissions import IsProjectOwner
from .serializers import (
    MagvisImageAssetSerializer,
    MagvisProjectSerializer,
    MagvisTopicQueueSerializer,
)


class _BaseAuth:
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsProjectOwner]


class MagvisProjectViewSet(_BaseAuth, viewsets.ModelViewSet):
    serializer_class = MagvisProjectSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return MagvisProject.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # ---------- Aktionen --------------------------------------------------

    @action(detail=False, methods=['post'], url_path='from_queue')
    def from_queue(self, request):
        """Erstellt ein Projekt aus dem nächsten pending Queue-Topic."""
        item = MagvisTopicQueue.pop_next(request.user)
        if not item:
            return Response({'detail': 'Themen-Queue ist leer'}, status=404)

        project = MagvisProject.objects.create(
            user=request.user,
            title=item.topic[:255],
            topic=item.topic,
            keywords=item.keywords,
            target_audience=item.target_audience,
            scheduled_at=request.data.get('scheduled_at'),
            auto_advance=request.data.get('auto_advance', True),
            source_queue_item=item,
        )
        if project.scheduled_at:
            from .tasks import schedule_project
            schedule_project(project)
        elif project.auto_advance:
            from .tasks import run_full_chain
            run_full_chain.delay(str(project.id))
        return Response(MagvisProjectSerializer(project).data, status=201)

    @action(detail=True, methods=['post'])
    def advance(self, request, id=None):
        project = self.get_object()
        slug = project.next_stage_slug()
        if not slug:
            return Response({'detail': 'Kein nächster Stage'}, status=400)
        from .tasks import run_stage_async
        result = run_stage_async.delay(str(project.id), slug)
        return Response({'task_id': result.id, 'stage': slug})

    @action(detail=True, methods=['post'], url_path=r'stage/(?P<slug>[\w_-]+)')
    def run_stage(self, request, id=None, slug=None):
        from .tasks import run_stage_async
        result = run_stage_async.delay(str(id), slug, kwargs=request.data or {})
        return Response({'task_id': result.id, 'stage': slug})

    @action(detail=True, methods=['get'], url_path=r'stage/(?P<slug>[\w_-]+)/status')
    def stage_status(self, request, id=None, slug=None):
        project = self.get_object()
        task_id = (project.task_ids or {}).get(slug)
        if not task_id:
            return Response({'state': 'not_started', 'progress_pct': project.progress_pct})
        ar = AsyncResult(task_id)
        return Response({
            'state': ar.state, 'info': str(ar.info) if ar.info else '',
            'progress_pct': project.progress_pct, 'stage': project.stage,
            'error_message': project.error_message,
        })

    @action(detail=True, methods=['post'])
    def schedule(self, request, id=None):
        project = self.get_object()
        scheduled_at = request.data.get('scheduled_at')
        if not scheduled_at:
            return Response({'detail': 'scheduled_at ist erforderlich'}, status=400)
        project.scheduled_at = scheduled_at
        project.save(update_fields=['scheduled_at'])
        from .tasks import schedule_project
        task_id = schedule_project(project)
        return Response({'celery_eta_task_id': task_id, 'scheduled_at': project.scheduled_at})

    @action(detail=True, methods=['post'])
    def cancel(self, request, id=None):
        project = self.get_object()
        if project.celery_eta_task_id:
            try:
                AsyncResult(project.celery_eta_task_id).revoke(terminate=False)
            except Exception:
                pass
        project.celery_eta_task_id = ''
        if project.stage == project.STAGE_SCHEDULED:
            project.stage = project.STAGE_CREATED
        project.save(update_fields=['celery_eta_task_id', 'stage'])
        return Response({'cancelled': True})

    @action(detail=True, methods=['post'], url_path='send_report')
    def send_report(self, request, id=None):
        project = self.get_object()
        from .services.report_mailer import send_project_report
        ok = send_project_report(project)
        return Response({'sent': ok})


class MagvisImageAssetViewSet(_BaseAuth, viewsets.ModelViewSet):
    serializer_class = MagvisImageAssetSerializer

    def get_queryset(self):
        return MagvisImageAsset.objects.filter(project__user=self.request.user).order_by('source', 'id')

    @action(detail=True, methods=['post'], url_path='post_to_socials')
    def post_to_socials(self, request, pk=None):
        asset = self.get_object()
        platforms = request.data.get('platforms') or []
        from .tasks import post_image_async
        result = post_image_async.delay(
            asset.id, platforms,
            request.data.get('use_overlay', False),
            request.data.get('overlay_text', ''),
            request.data.get('overlay_method', 'pil'),
            request.data.get('title', ''),
            request.data.get('description', ''),
        )
        return Response({'task_id': result.id})


class MagvisTopicQueueViewSet(_BaseAuth, viewsets.ModelViewSet):
    serializer_class = MagvisTopicQueueSerializer

    def get_queryset(self):
        qs = MagvisTopicQueue.objects.filter(user=self.request.user)
        st = self.request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        items = request.data.get('items') or []
        if isinstance(items, str):  # CSV-Variante: pro Zeile ein Topic
            items = [{'topic': line.strip()} for line in items.splitlines() if line.strip()]
        created = []
        for it in items:
            obj = MagvisTopicQueue.objects.create(
                user=request.user,
                topic=it.get('topic', '')[:500],
                keywords=it.get('keywords', []) or [],
                target_audience=it.get('target_audience', ''),
                priority=it.get('priority', 100),
                notes=it.get('notes', ''),
            )
            created.append(obj.id)
        return Response({'created_ids': created, 'count': len(created)}, status=201)

    @action(detail=False, methods=['get'])
    def next(self, request):
        item = MagvisTopicQueue.peek_next(request.user)
        if not item:
            return Response({'detail': 'Queue leer'}, status=404)
        return Response(MagvisTopicQueueSerializer(item).data)

    @action(detail=False, methods=['post'])
    def pop(self, request):
        item = MagvisTopicQueue.pop_next(request.user)
        if not item:
            return Response({'detail': 'Queue leer'}, status=404)
        return Response(MagvisTopicQueueSerializer(item).data)

    @action(detail=True, methods=['post'])
    def skip(self, request, pk=None):
        item = self.get_object()
        item.status = MagvisTopicQueue.STATUS_SKIPPED
        item.save(update_fields=['status'])
        return Response({'status': item.status})

    @action(detail=True, methods=['post'])
    def reset(self, request, pk=None):
        item = self.get_object()
        item.status = MagvisTopicQueue.STATUS_PENDING
        item.used_at = None
        item.save(update_fields=['status', 'used_at'])
        return Response({'status': item.status})
