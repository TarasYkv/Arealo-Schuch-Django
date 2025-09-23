"""
LoomLine ViewSets - REST API Views
Comprehensive API viewsets for all LoomLine functionality with proper permissions
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import timedelta

from .models import (
    Project, TaskEntry, TimelineEntry, Comment,
    SEOMetrics, ProjectInvitation
)
from .serializers import (
    ProjectListSerializer, ProjectDetailSerializer,
    TaskEntryListSerializer, TaskEntryDetailSerializer,
    TimelineEntrySerializer, CommentSerializer,
    SEOMetricsSerializer, ProjectInvitationSerializer,
    ProjectInvitationResponseSerializer, DashboardSerializer,
    ProjectStatsSerializer, TaskStatsSerializer
)
from .permissions import ProjectAccessPermission, TaskAccessPermission


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Project management
    Handles CRUD operations and collaboration features
    """

    permission_classes = [IsAuthenticated, ProjectAccessPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'domain']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        """Get projects the user has access to"""
        user = self.request.user
        return Project.objects.filter(
            Q(owner=user) | Q(members=user)
        ).distinct().select_related('owner').prefetch_related('members')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectListSerializer

    def perform_create(self, serializer):
        """Create project with current user as owner"""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """Add a member to the project"""
        project = self.get_object()

        # Only owner can add members
        if project.owner != request.user:
            return Response(
                {'error': 'Only project owner can add members'},
                status=status.HTTP_403_FORBIDDEN
            )

        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Check if user is already owner or member
            if project.owner == user:
                return Response(
                    {'error': 'User is already the project owner'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if project.members.filter(id=user.id).exists():
                return Response(
                    {'error': 'User is already a project member'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            project.members.add(user)
            return Response(
                {'message': f'User {user.username} added to project'},
                status=status.HTTP_200_OK
            )

        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        """Remove a member from the project"""
        project = self.get_object()

        # Only owner can remove members
        if project.owner != request.user:
            return Response(
                {'error': 'Only project owner can remove members'},
                status=status.HTTP_403_FORBIDDEN
            )

        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)

            if not project.members.filter(id=user.id).exists():
                return Response(
                    {'error': 'User is not a project member'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            project.members.remove(user)
            return Response(
                {'message': f'User {user.username} removed from project'},
                status=status.HTTP_200_OK
            )

        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Get project timeline (all task activities)"""
        project = self.get_object()

        # Get timeline entries for all tasks in project
        timeline_entries = TimelineEntry.objects.filter(
            task__project=project
        ).select_related('task', 'user').order_by('-timestamp')

        # Apply pagination
        page = self.paginate_queryset(timeline_entries)
        if page is not None:
            serializer = TimelineEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = TimelineEntrySerializer(timeline_entries, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get project statistics"""
        project = self.get_object()

        tasks = project.tasks.all()
        stats = {
            'total_tasks': tasks.count(),
            'tasks_by_status': {
                'todo': tasks.filter(status='todo').count(),
                'in_progress': tasks.filter(status='in_progress').count(),
                'review': tasks.filter(status='review').count(),
                'done': tasks.filter(status='done').count(),
                'cancelled': tasks.filter(status='cancelled').count(),
            },
            'tasks_by_category': {},
            'tasks_by_priority': {},
            'overdue_tasks': tasks.filter(
                due_date__lt=timezone.now(),
                status__in=['todo', 'in_progress', 'review']
            ).count(),
            'total_comments': Comment.objects.filter(task__project=project).count(),
            'total_metrics': SEOMetrics.objects.filter(task__project=project).count(),
        }

        # Tasks by category
        for choice in TaskEntry.CATEGORY_CHOICES:
            category = choice[0]
            stats['tasks_by_category'][category] = tasks.filter(category=category).count()

        # Tasks by priority
        for choice in TaskEntry.PRIORITY_CHOICES:
            priority = choice[0]
            stats['tasks_by_priority'][priority] = tasks.filter(priority=priority).count()

        return Response(stats)


class TaskEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for TaskEntry management
    Handles CRUD operations and task-specific features
    """

    permission_classes = [IsAuthenticated, TaskAccessPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'priority', 'status', 'due_date', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get tasks the user has access to"""
        user = self.request.user
        return TaskEntry.objects.filter(
            Q(project__owner=user) | Q(project__members=user)
        ).distinct().select_related('project', 'author', 'assignee')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return TaskEntryDetailSerializer
        return TaskEntryListSerializer

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign task to a user"""
        task = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            assignee = User.objects.get(id=user_id)

            # Check if user has access to the project
            if not task.project.user_has_access(assignee):
                return Response(
                    {'error': 'User does not have access to this project'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            old_assignee = task.assignee
            task.assignee = assignee
            task.save()

            # Create timeline entry
            TimelineEntry.objects.create(
                task=task,
                user=request.user,
                action='assigned',
                description=f'Task assigned to {assignee.username}',
                previous_value={'assignee': old_assignee.username if old_assignee else None},
                new_value={'assignee': assignee.username}
            )

            return Response(
                {'message': f'Task assigned to {assignee.username}'},
                status=status.HTTP_200_OK
            )

        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def unassign(self, request, pk=None):
        """Unassign task"""
        task = self.get_object()
        old_assignee = task.assignee

        if not old_assignee:
            return Response(
                {'error': 'Task is not assigned to anyone'},
                status=status.HTTP_400_BAD_REQUEST
            )

        task.assignee = None
        task.save()

        # Create timeline entry
        TimelineEntry.objects.create(
            task=task,
            user=request.user,
            action='assigned',
            description='Task unassigned',
            previous_value={'assignee': old_assignee.username},
            new_value={'assignee': None}
        )

        return Response(
            {'message': 'Task unassigned'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        """Get tasks assigned to current user"""
        tasks = self.get_queryset().filter(assignee=request.user)

        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue tasks"""
        tasks = self.get_queryset().filter(
            due_date__lt=timezone.now(),
            status__in=['todo', 'in_progress', 'review']
        )

        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Comment management
    Handles task comments and discussions
    """

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['created_at']

    def get_queryset(self):
        """Get comments the user has access to"""
        user = self.request.user
        return Comment.objects.filter(
            Q(task__project__owner=user) | Q(task__project__members=user)
        ).distinct().select_related('task', 'author')


class TimelineEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for TimelineEntry (read-only)
    Provides timeline and activity history
    """

    serializer_class = TimelineEntrySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_queryset(self):
        """Get timeline entries the user has access to"""
        user = self.request.user
        return TimelineEntry.objects.filter(
            Q(task__project__owner=user) | Q(task__project__members=user)
        ).distinct().select_related('task', 'user')


class SEOMetricsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SEOMetrics management
    Handles SEO performance tracking and metrics
    """

    serializer_class = SEOMetricsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['recorded_at']
    ordering = ['-recorded_at']

    def get_queryset(self):
        """Get SEO metrics the user has access to"""
        user = self.request.user
        return SEOMetrics.objects.filter(
            Q(task__project__owner=user) | Q(task__project__members=user)
        ).distinct().select_related('task')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get SEO metrics summary"""
        queryset = self.get_queryset()

        # Get metrics for specified task or project
        task_id = request.query_params.get('task_id')
        project_id = request.query_params.get('project_id')

        if task_id:
            queryset = queryset.filter(task_id=task_id)
        elif project_id:
            queryset = queryset.filter(task__project_id=project_id)

        latest_metrics = queryset.order_by('url', '-recorded_at').distinct('url')

        summary = {
            'total_urls': queryset.values('url').distinct().count(),
            'total_records': queryset.count(),
            'latest_metrics': SEOMetricsSerializer(latest_metrics, many=True).data
        }

        return Response(summary)


class ProjectInvitationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ProjectInvitation management
    Handles project collaboration invitations
    """

    serializer_class = ProjectInvitationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get invitations relevant to the user"""
        user = self.request.user
        return ProjectInvitation.objects.filter(
            Q(invited_by=user) | Q(invited_user=user)
        ).select_related('project', 'invited_by', 'invited_user')

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending invitations for current user"""
        invitations = self.get_queryset().filter(
            invited_user=request.user,
            status='pending'
        )

        serializer = self.get_serializer(invitations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """Respond to an invitation (accept/decline)"""
        invitation = self.get_object()

        # Only invited user can respond
        if invitation.invited_user != request.user:
            return Response(
                {'error': 'Only invited user can respond to invitation'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ProjectInvitationResponseSerializer(
            invitation, data=request.data
        )
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()

        return Response(
            ProjectInvitationSerializer(invitation).data,
            status=status.HTTP_200_OK
        )


class DashboardViewSet(viewsets.ViewSet):
    """
    ViewSet for Dashboard data
    Provides aggregated statistics and recent activity
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get dashboard statistics"""
        user = request.user

        # Project stats
        user_projects = Project.objects.filter(
            Q(owner=user) | Q(members=user)
        ).distinct()

        project_stats = {
            'total_projects': user_projects.count(),
            'active_projects': user_projects.filter(is_active=True).count(),
            'owned_projects': user_projects.filter(owner=user).count(),
            'member_projects': user_projects.filter(members=user).exclude(owner=user).count(),
        }

        # Task stats
        user_tasks = TaskEntry.objects.filter(
            Q(project__owner=user) | Q(project__members=user)
        ).distinct()

        task_stats = {
            'total_tasks': user_tasks.count(),
            'todo_tasks': user_tasks.filter(status='todo').count(),
            'in_progress_tasks': user_tasks.filter(status='in_progress').count(),
            'review_tasks': user_tasks.filter(status='review').count(),
            'completed_tasks': user_tasks.filter(status='done').count(),
            'overdue_tasks': user_tasks.filter(
                due_date__lt=timezone.now(),
                status__in=['todo', 'in_progress', 'review']
            ).count(),
        }

        # Recent data
        recent_projects = user_projects.order_by('-updated_at')[:5]
        recent_tasks = user_tasks.order_by('-created_at')[:10]
        pending_invitations = ProjectInvitation.objects.filter(
            invited_user=user,
            status='pending'
        )[:5]

        dashboard_data = {
            'project_stats': project_stats,
            'task_stats': task_stats,
            'recent_projects': ProjectListSerializer(recent_projects, many=True, context={'request': request}).data,
            'recent_tasks': TaskEntryListSerializer(recent_tasks, many=True, context={'request': request}).data,
            'pending_invitations': ProjectInvitationSerializer(pending_invitations, many=True, context={'request': request}).data,
        }

        return Response(dashboard_data)

    @action(detail=False, methods=['get'])
    def activity(self, request):
        """Get recent activity timeline"""
        user = request.user

        # Get recent timeline entries from user's projects
        timeline_entries = TimelineEntry.objects.filter(
            Q(task__project__owner=user) | Q(task__project__members=user)
        ).distinct().select_related('task', 'user').order_by('-timestamp')[:20]

        serializer = TimelineEntrySerializer(timeline_entries, many=True)
        return Response(serializer.data)