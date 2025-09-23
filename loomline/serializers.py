"""
LoomLine Serializers - REST API Serialization
Comprehensive serializers for all LoomLine models with proper validation
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import (
    Project, TaskEntry, TimelineEntry, Comment,
    SEOMetrics, ProjectInvitation
)

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for references"""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class ProjectMemberSerializer(serializers.ModelSerializer):
    """Serializer for project members with additional info"""

    full_name = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'is_online']
        read_only_fields = ['id']

    def get_full_name(self, obj):
        """Get user's full name"""
        return obj.get_full_name() or obj.username

    def get_is_online(self, obj):
        """Get user's online status"""
        if hasattr(obj, 'is_currently_online'):
            return obj.is_currently_online()
        return False


class ProjectListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for project lists"""

    owner = UserBasicSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'domain', 'owner',
            'member_count', 'task_count', 'user_role',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        """Get number of project members"""
        return obj.members.count()

    def get_task_count(self, obj):
        """Get number of tasks in project"""
        return obj.tasks.count()

    def get_user_role(self, obj):
        """Get current user's role in project"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        if obj.owner == request.user:
            return 'owner'
        elif obj.members.filter(id=request.user.id).exists():
            return 'member'
        return None


class ProjectDetailSerializer(serializers.ModelSerializer):
    """Detailed project serializer with full information"""

    owner = UserBasicSerializer(read_only=True)
    members = ProjectMemberSerializer(many=True, read_only=True)
    user_role = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()
    task_summary = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'domain', 'owner', 'members',
            'user_role', 'participant_count', 'task_summary',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']

    def get_user_role(self, obj):
        """Get current user's role in project"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        if obj.owner == request.user:
            return 'owner'
        elif obj.members.filter(id=request.user.id).exists():
            return 'member'
        return None

    def get_participant_count(self, obj):
        """Get total number of participants (owner + members)"""
        return obj.members.count() + 1  # +1 for owner

    def get_task_summary(self, obj):
        """Get task summary statistics"""
        tasks = obj.tasks.all()
        return {
            'total': tasks.count(),
            'todo': tasks.filter(status='todo').count(),
            'in_progress': tasks.filter(status='in_progress').count(),
            'review': tasks.filter(status='review').count(),
            'done': tasks.filter(status='done').count(),
            'cancelled': tasks.filter(status='cancelled').count(),
        }

    def create(self, validated_data):
        """Create project with current user as owner"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['owner'] = request.user
        return super().create(validated_data)


class TaskEntryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for task lists"""

    author = UserBasicSerializer(read_only=True)
    assignee = UserBasicSerializer(read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    comment_count = serializers.SerializerMethodField()
    metrics_count = serializers.SerializerMethodField()

    class Meta:
        model = TaskEntry
        fields = [
            'id', 'title', 'description', 'category', 'priority', 'status',
            'project', 'project_name', 'author', 'assignee',
            'due_date', 'comment_count', 'metrics_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']

    def get_comment_count(self, obj):
        """Get number of comments on task"""
        return obj.comments.count()

    def get_metrics_count(self, obj):
        """Get number of SEO metrics records for task"""
        return obj.seo_metrics.count()


class TaskEntryDetailSerializer(serializers.ModelSerializer):
    """Detailed task serializer with full information"""

    author = UserBasicSerializer(read_only=True)
    assignee = UserBasicSerializer(read_only=True)
    project = ProjectListSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True)
    assignee_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    comments = serializers.SerializerMethodField()
    timeline_entries = serializers.SerializerMethodField()
    latest_metrics = serializers.SerializerMethodField()

    class Meta:
        model = TaskEntry
        fields = [
            'id', 'title', 'description', 'category', 'priority', 'status',
            'project', 'project_id', 'author', 'assignee', 'assignee_id',
            'due_date', 'estimated_hours', 'actual_hours',
            'comments', 'timeline_entries', 'latest_metrics',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at', 'completed_at']

    def get_comments(self, obj):
        """Get recent comments for task"""
        recent_comments = obj.comments.select_related('author').order_by('-created_at')[:5]
        return CommentSerializer(recent_comments, many=True).data

    def get_timeline_entries(self, obj):
        """Get recent timeline entries for task"""
        recent_entries = obj.timeline_entries.select_related('user').order_by('-timestamp')[:10]
        return TimelineEntrySerializer(recent_entries, many=True).data

    def get_latest_metrics(self, obj):
        """Get latest SEO metrics for task"""
        latest_metric = obj.seo_metrics.order_by('-recorded_at').first()
        if latest_metric:
            return SEOMetricsSerializer(latest_metric).data
        return None

    def create(self, validated_data):
        """Create task with current user as author"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user

        # Handle assignee_id
        assignee_id = validated_data.pop('assignee_id', None)
        if assignee_id:
            try:
                assignee = User.objects.get(id=assignee_id)
                validated_data['assignee'] = assignee
            except User.DoesNotExist:
                raise serializers.ValidationError({'assignee_id': 'Invalid user ID'})

        # Handle project_id
        project_id = validated_data.pop('project_id')
        try:
            project = Project.objects.get(id=project_id)
            # Check if user has access to project
            if not project.user_has_access(request.user):
                raise serializers.ValidationError({'project_id': 'No access to this project'})
            validated_data['project'] = project
        except Project.DoesNotExist:
            raise serializers.ValidationError({'project_id': 'Invalid project ID'})

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update task with timeline tracking"""
        # Handle assignee_id
        assignee_id = validated_data.pop('assignee_id', None)
        if assignee_id is not None:
            if assignee_id:
                try:
                    assignee = User.objects.get(id=assignee_id)
                    validated_data['assignee'] = assignee
                except User.DoesNotExist:
                    raise serializers.ValidationError({'assignee_id': 'Invalid user ID'})
            else:
                validated_data['assignee'] = None

        # Track status changes for timeline
        old_status = instance.status
        new_status = validated_data.get('status', old_status)

        # Update instance
        instance = super().update(instance, validated_data)

        # Create timeline entry for status change
        if old_status != new_status:
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                TimelineEntry.objects.create(
                    task=instance,
                    user=request.user,
                    action='status_changed',
                    description=f'Status changed from "{old_status}" to "{new_status}"',
                    previous_value={'status': old_status},
                    new_value={'status': new_status}
                )

        return instance

    def validate_project_id(self, value):
        """Validate project access"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError('Authentication required')

        try:
            project = Project.objects.get(id=value)
            if not project.user_has_access(request.user):
                raise serializers.ValidationError('No access to this project')
        except Project.DoesNotExist:
            raise serializers.ValidationError('Project does not exist')

        return value


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for task comments"""

    author = UserBasicSerializer(read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = Comment
        fields = [
            'id', 'task', 'task_title', 'author', 'content',
            'is_edited', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'is_edited', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create comment with current user as author"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user

        # Check if user has access to the task's project
        task = validated_data['task']
        if not task.project.user_has_access(request.user):
            raise serializers.ValidationError('No access to this task')

        comment = super().create(validated_data)

        # Create timeline entry
        TimelineEntry.objects.create(
            task=task,
            user=request.user,
            action='commented',
            description=f'Added comment: {comment.content[:100]}...'
        )

        return comment


class TimelineEntrySerializer(serializers.ModelSerializer):
    """Serializer for timeline entries"""

    user = UserBasicSerializer(read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = TimelineEntry
        fields = [
            'id', 'task', 'task_title', 'user', 'action', 'description',
            'previous_value', 'new_value', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class SEOMetricsSerializer(serializers.ModelSerializer):
    """Serializer for SEO metrics"""

    task_title = serializers.CharField(source='task.title', read_only=True)
    keyword_summary = serializers.SerializerMethodField()
    cwv_summary = serializers.SerializerMethodField()

    class Meta:
        model = SEOMetrics
        fields = [
            'id', 'task', 'task_title', 'url',
            'organic_traffic', 'total_impressions', 'total_clicks',
            'average_ctr', 'average_position', 'keyword_rankings',
            'keyword_summary', 'page_load_speed', 'core_web_vitals',
            'cwv_summary', 'total_backlinks', 'referring_domains',
            'domain_authority', 'notes', 'recorded_at'
        ]
        read_only_fields = ['id', 'recorded_at']

    def get_keyword_summary(self, obj):
        """Get keyword ranking summary"""
        return obj.get_keyword_ranking_summary()

    def get_cwv_summary(self, obj):
        """Get Core Web Vitals summary"""
        return obj.get_core_web_vitals_summary()

    def validate_task(self, value):
        """Validate task access"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError('Authentication required')

        if not value.project.user_has_access(request.user):
            raise serializers.ValidationError('No access to this task')

        return value


class ProjectInvitationSerializer(serializers.ModelSerializer):
    """Serializer for project invitations"""

    project = ProjectListSerializer(read_only=True)
    invited_by = UserBasicSerializer(read_only=True)
    invited_user = UserBasicSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True)
    invited_user_id = serializers.IntegerField(write_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = ProjectInvitation
        fields = [
            'id', 'project', 'project_id', 'invited_by', 'invited_user',
            'invited_user_id', 'email', 'status', 'message',
            'is_expired', 'created_at', 'responded_at', 'expires_at'
        ]
        read_only_fields = ['id', 'invited_by', 'created_at', 'responded_at']

    def get_is_expired(self, obj):
        """Check if invitation is expired"""
        return obj.is_expired()

    def create(self, validated_data):
        """Create invitation with validation"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError('Authentication required')

        # Set invited_by
        validated_data['invited_by'] = request.user

        # Handle project_id
        project_id = validated_data.pop('project_id')
        try:
            project = Project.objects.get(id=project_id)
            if project.owner != request.user:
                raise serializers.ValidationError({'project_id': 'Only project owner can send invitations'})
            validated_data['project'] = project
        except Project.DoesNotExist:
            raise serializers.ValidationError({'project_id': 'Project does not exist'})

        # Handle invited_user_id
        invited_user_id = validated_data.pop('invited_user_id')
        try:
            invited_user = User.objects.get(id=invited_user_id)
            validated_data['invited_user'] = invited_user
            validated_data['email'] = invited_user.email
        except User.DoesNotExist:
            raise serializers.ValidationError({'invited_user_id': 'User does not exist'})

        # Check if user is already a member
        if project.members.filter(id=invited_user.id).exists() or project.owner == invited_user:
            raise serializers.ValidationError('User is already a project member')

        # Check for existing pending invitation
        existing = ProjectInvitation.objects.filter(
            project=project,
            invited_user=invited_user,
            status='pending'
        ).exists()

        if existing:
            raise serializers.ValidationError('Pending invitation already exists for this user')

        # Set expiration date (7 days from now)
        validated_data['expires_at'] = timezone.now() + timedelta(days=7)

        return super().create(validated_data)


class ProjectInvitationResponseSerializer(serializers.Serializer):
    """Serializer for responding to project invitations"""

    action = serializers.ChoiceField(choices=['accept', 'decline'])

    def validate(self, data):
        """Validate invitation response"""
        invitation = self.instance
        if not invitation:
            raise serializers.ValidationError('No invitation provided')

        if invitation.status != 'pending':
            raise serializers.ValidationError('Invitation is no longer pending')

        if invitation.is_expired():
            raise serializers.ValidationError('Invitation has expired')

        return data

    def save(self):
        """Process invitation response"""
        invitation = self.instance
        action = self.validated_data['action']

        if action == 'accept':
            success = invitation.accept()
            if not success:
                raise serializers.ValidationError('Failed to accept invitation')
        else:
            success = invitation.decline()
            if not success:
                raise serializers.ValidationError('Failed to decline invitation')

        return invitation


# Statistics and Dashboard Serializers

class ProjectStatsSerializer(serializers.Serializer):
    """Serializer for project statistics"""

    total_projects = serializers.IntegerField()
    active_projects = serializers.IntegerField()
    owned_projects = serializers.IntegerField()
    member_projects = serializers.IntegerField()


class TaskStatsSerializer(serializers.Serializer):
    """Serializer for task statistics"""

    total_tasks = serializers.IntegerField()
    todo_tasks = serializers.IntegerField()
    in_progress_tasks = serializers.IntegerField()
    review_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    """Serializer for dashboard data"""

    project_stats = ProjectStatsSerializer()
    task_stats = TaskStatsSerializer()
    recent_projects = ProjectListSerializer(many=True)
    recent_tasks = TaskEntryListSerializer(many=True)
    pending_invitations = ProjectInvitationSerializer(many=True)