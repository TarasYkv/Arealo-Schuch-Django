"""
LoomLine Signals - Automatic Timeline Tracking
Django signals for automated timeline entry creation
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import TaskEntry, Comment, SEOMetrics, TimelineEntry

User = get_user_model()


@receiver(post_save, sender=TaskEntry)
def create_task_timeline_entry(sender, instance, created, **kwargs):
    """Create timeline entry when a task is created or updated"""
    if created:
        # Task was just created
        TimelineEntry.objects.create(
            task=instance,
            user=instance.author,
            action='created',
            description=f'Task "{instance.title}" was created'
        )
    else:
        # Task was updated - we could track specific field changes here
        # For now, we'll create a generic update entry
        # Note: More sophisticated change tracking would require
        # comparing old vs new values, which can be done with django-model-utils
        pass


@receiver(post_save, sender=Comment)
def create_comment_timeline_entry(sender, instance, created, **kwargs):
    """Create timeline entry when a comment is added"""
    if created:
        # Truncate comment content for timeline display
        content_preview = instance.content[:100] + "..." if len(instance.content) > 100 else instance.content

        TimelineEntry.objects.create(
            task=instance.task,
            user=instance.author,
            action='commented',
            description=f'Added comment: {content_preview}'
        )


@receiver(post_save, sender=SEOMetrics)
def create_metrics_timeline_entry(sender, instance, created, **kwargs):
    """Create timeline entry when SEO metrics are recorded"""
    if created:
        description = f'Recorded SEO metrics for {instance.url}'

        # Add specific metric highlights if available
        highlights = []
        if instance.organic_traffic:
            highlights.append(f'{instance.organic_traffic} organic sessions')
        if instance.keyword_rankings:
            keyword_count = len(instance.keyword_rankings)
            highlights.append(f'{keyword_count} keyword rankings')
        if instance.page_load_speed:
            highlights.append(f'{instance.page_load_speed}s load time')

        if highlights:
            description += f' ({", ".join(highlights)})'

        # We need to get the current user somehow for this signal
        # Since we don't have request context, we'll need to set this
        # in the view or pass it through the model save method
        # For now, we'll use the task author as fallback
        user = getattr(instance, '_current_user', instance.task.author)

        TimelineEntry.objects.create(
            task=instance.task,
            user=user,
            action='updated',
            description=description
        )


@receiver(post_delete, sender=TaskEntry)
def create_task_deletion_timeline_entry(sender, instance, **kwargs):
    """Create timeline entry when a task is deleted"""
    # Note: Since the task is being deleted, we can't create a timeline entry
    # that references it. In a real application, you might want to:
    # 1. Soft delete tasks instead of hard delete
    # 2. Create project-level timeline entries for deletions
    # 3. Use a separate audit log system
    pass


@receiver(post_delete, sender=Comment)
def create_comment_deletion_timeline_entry(sender, instance, **kwargs):
    """Create timeline entry when a comment is deleted"""
    # Similar to task deletion, we need to handle this carefully
    # since the comment is being deleted
    try:
        TimelineEntry.objects.create(
            task=instance.task,
            user=instance.author,  # This might not be the user who deleted it
            action='updated',
            description=f'A comment was deleted'
        )
    except Exception:
        # If task is also being deleted, this will fail
        pass


# Custom signal handlers for specific business logic

def create_status_change_timeline_entry(task, old_status, new_status, user):
    """
    Helper function to create timeline entry for status changes
    This should be called manually from views when status changes
    """
    status_display_map = dict(TaskEntry.STATUS_CHOICES)

    TimelineEntry.objects.create(
        task=task,
        user=user,
        action='status_changed',
        description=f'Status changed from "{status_display_map.get(old_status, old_status)}" to "{status_display_map.get(new_status, new_status)}"',
        previous_value={'status': old_status},
        new_value={'status': new_status}
    )


def create_assignment_timeline_entry(task, old_assignee, new_assignee, user):
    """
    Helper function to create timeline entry for task assignments
    This should be called manually from views when assignments change
    """
    if old_assignee and new_assignee:
        description = f'Reassigned from {old_assignee.get_full_name() or old_assignee.username} to {new_assignee.get_full_name() or new_assignee.username}'
    elif new_assignee:
        description = f'Assigned to {new_assignee.get_full_name() or new_assignee.username}'
    elif old_assignee:
        description = f'Unassigned from {old_assignee.get_full_name() or old_assignee.username}'
    else:
        description = 'Assignment updated'

    TimelineEntry.objects.create(
        task=task,
        user=user,
        action='assigned',
        description=description,
        previous_value={'assignee': old_assignee.username if old_assignee else None},
        new_value={'assignee': new_assignee.username if new_assignee else None}
    )


def create_priority_change_timeline_entry(task, old_priority, new_priority, user):
    """
    Helper function to create timeline entry for priority changes
    """
    priority_display_map = dict(TaskEntry.PRIORITY_CHOICES)

    TimelineEntry.objects.create(
        task=task,
        user=user,
        action='updated',
        description=f'Priority changed from "{priority_display_map.get(old_priority, old_priority)}" to "{priority_display_map.get(new_priority, new_priority)}"',
        previous_value={'priority': old_priority},
        new_value={'priority': new_priority}
    )


def create_due_date_change_timeline_entry(task, old_due_date, new_due_date, user):
    """
    Helper function to create timeline entry for due date changes
    """
    if old_due_date and new_due_date:
        description = f'Due date changed from {old_due_date.strftime("%Y-%m-%d %H:%M")} to {new_due_date.strftime("%Y-%m-%d %H:%M")}'
    elif new_due_date:
        description = f'Due date set to {new_due_date.strftime("%Y-%m-%d %H:%M")}'
    elif old_due_date:
        description = f'Due date removed (was {old_due_date.strftime("%Y-%m-%d %H:%M")})'
    else:
        description = 'Due date updated'

    TimelineEntry.objects.create(
        task=task,
        user=user,
        action='updated',
        description=description,
        previous_value={'due_date': old_due_date.isoformat() if old_due_date else None},
        new_value={'due_date': new_due_date.isoformat() if new_due_date else None}
    )