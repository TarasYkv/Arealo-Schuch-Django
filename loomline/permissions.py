"""
LoomLine Permissions - Custom Permission Classes
Fine-grained access control for LoomLine models
"""

from rest_framework import permissions
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from .models import Project, TaskEntry


class ProjectAccessPermission(permissions.BasePermission):
    """
    Custom permission for Project access
    - Owners can perform all operations
    - Members can view and perform limited operations
    - Non-participants have no access
    """

    def has_permission(self, request, view):
        """Check if user has permission to access projects"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access specific project"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has access to the project
        if not obj.user_has_access(request.user):
            return False

        # Owner can do everything
        if obj.owner == request.user:
            return True

        # Members have limited permissions
        if obj.members.filter(id=request.user.id).exists():
            # Members can read, but limited write access
            if view.action in ['retrieve', 'list', 'timeline', 'stats']:
                return True

            # Members can update project details but not delete
            if view.action in ['update', 'partial_update']:
                return True

            # Only owner can delete, add/remove members
            if view.action in ['destroy', 'add_member', 'remove_member']:
                return False

            return True

        return False


class TaskAccessPermission(permissions.BasePermission):
    """
    Custom permission for TaskEntry access
    - Project participants can access tasks within their projects
    - Authors and assignees have additional permissions
    """

    def has_permission(self, request, view):
        """Check if user has permission to access tasks"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access specific task"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has access to the project
        if not obj.project.user_has_access(request.user):
            return False

        # Project owner can do everything
        if obj.project.owner == request.user:
            return True

        # Task author can do everything with their tasks
        if obj.author == request.user:
            return True

        # Task assignee can update and comment on assigned tasks
        if obj.assignee == request.user:
            if view.action in ['retrieve', 'update', 'partial_update', 'assign', 'unassign']:
                return True

        # Project members can read and create tasks
        if obj.project.members.filter(id=request.user.id).exists():
            if view.action in ['retrieve', 'list', 'create']:
                return True

            # Members can update tasks but with some restrictions
            if view.action in ['update', 'partial_update']:
                return True

            # Only author or project owner can delete
            if view.action == 'destroy':
                return False

            return True

        return False


class CommentAccessPermission(permissions.BasePermission):
    """
    Custom permission for Comment access
    - Project participants can access comments
    - Authors can edit/delete their own comments
    """

    def has_permission(self, request, view):
        """Check if user has permission to access comments"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access specific comment"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has access to the task's project
        if not obj.task.project.user_has_access(request.user):
            return False

        # Comment author can edit/delete their own comments
        if obj.author == request.user:
            return True

        # Project owner can manage all comments
        if obj.task.project.owner == request.user:
            return True

        # Project members can read comments and create new ones
        if obj.task.project.members.filter(id=request.user.id).exists():
            if view.action in ['retrieve', 'list', 'create']:
                return True

            # Only author and project owner can edit/delete
            if view.action in ['update', 'partial_update', 'destroy']:
                return False

            return True

        return False


class SEOMetricsAccessPermission(permissions.BasePermission):
    """
    Custom permission for SEOMetrics access
    - Project participants can access metrics
    - Anyone with project access can create metrics
    """

    def has_permission(self, request, view):
        """Check if user has permission to access SEO metrics"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access specific SEO metrics"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has access to the task's project
        if not obj.task.project.user_has_access(request.user):
            return False

        # Project owner can do everything
        if obj.task.project.owner == request.user:
            return True

        # Project members can read and create metrics
        if obj.task.project.members.filter(id=request.user.id).exists():
            if view.action in ['retrieve', 'list', 'create', 'summary']:
                return True

            # Members can update metrics
            if view.action in ['update', 'partial_update']:
                return True

            # Only project owner can delete metrics
            if view.action == 'destroy':
                return False

            return True

        return False


class ProjectInvitationPermission(permissions.BasePermission):
    """
    Custom permission for ProjectInvitation access
    - Project owners can send invitations
    - Invited users can respond to invitations
    """

    def has_permission(self, request, view):
        """Check if user has permission to access invitations"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access specific invitation"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Invited user can view and respond to their invitations
        if obj.invited_user == request.user:
            if view.action in ['retrieve', 'respond']:
                return True
            # Invited users cannot edit invitation details
            return False

        # User who sent the invitation can view and manage it
        if obj.invited_by == request.user:
            if view.action in ['retrieve', 'update', 'partial_update', 'destroy']:
                return True
            return False

        # Project owner can view invitations for their projects
        if obj.project.owner == request.user:
            return True

        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Instance must have an attribute named 'owner'.
        return obj.owner == request.user


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow authors of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Instance must have an attribute named 'author'.
        return obj.author == request.user


class ProjectMemberPermission(permissions.BasePermission):
    """
    Permission that allows access to project members and owners
    """

    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user is project member or owner"""
        if hasattr(obj, 'project'):
            project = obj.project
        elif isinstance(obj, Project):
            project = obj
        else:
            return False

        return project.user_has_access(request.user)


class CanManageProjectMembers(permissions.BasePermission):
    """
    Permission that allows only project owners to manage members
    """

    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user is project owner"""
        if isinstance(obj, Project):
            return obj.owner == request.user
        elif hasattr(obj, 'project'):
            return obj.project.owner == request.user

        return False


class TaskAssigneePermission(permissions.BasePermission):
    """
    Permission for task assignees to perform specific actions
    """

    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user is task assignee, author, or project owner"""
        if not isinstance(obj, TaskEntry):
            return False

        # Task assignee can perform certain actions
        if obj.assignee == request.user:
            return True

        # Task author can always access
        if obj.author == request.user:
            return True

        # Project owner can always access
        if obj.project.owner == request.user:
            return True

        return False


def user_can_access_project(user, project_id):
    """
    Utility function to check if user can access a project
    """
    if not user or not user.is_authenticated:
        return False

    try:
        project = Project.objects.get(id=project_id)
        return project.user_has_access(user)
    except Project.DoesNotExist:
        return False


def user_can_access_task(user, task_id):
    """
    Utility function to check if user can access a task
    """
    if not user or not user.is_authenticated:
        return False

    try:
        task = TaskEntry.objects.select_related('project').get(id=task_id)
        return task.project.user_has_access(user)
    except TaskEntry.DoesNotExist:
        return False


def get_user_accessible_projects(user):
    """
    Get all projects that a user can access
    """
    if not user or not user.is_authenticated:
        return Project.objects.none()

    return Project.objects.filter(
        models.Q(owner=user) | models.Q(members=user)
    ).distinct()


def get_user_accessible_tasks(user):
    """
    Get all tasks that a user can access
    """
    if not user or not user.is_authenticated:
        return TaskEntry.objects.none()

    return TaskEntry.objects.filter(
        models.Q(project__owner=user) | models.Q(project__members=user)
    ).distinct()