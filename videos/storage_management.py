"""
Storage Management Service
Handles storage overage detection, grace periods, and notifications
"""

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from datetime import timedelta
import logging

from .models import UserStorage

User = get_user_model()
logger = logging.getLogger(__name__)


class StorageOverageService:
    """Service for managing storage overages and notifications"""
    
    @staticmethod
    def check_user_storage_overage(user):
        """Check if user has storage overage and handle accordingly"""
        try:
            storage = UserStorage.objects.get(user=user)
        except UserStorage.DoesNotExist:
            # Create default storage for user
            storage = UserStorage.objects.create(user=user)
        
        if not storage.is_storage_exceeded():
            # Clear overage status if storage is back within limits
            if storage.is_in_grace_period or storage.overage_restriction_level > 0:
                storage.clear_overage_status()
                logger.info(f"Storage overage cleared for user {user.username}")
            return False
        
        # Storage is exceeded - handle based on current status
        if not storage.is_in_grace_period and storage.overage_restriction_level == 0:
            # First time overage detected - start grace period
            storage.start_grace_period()
            StorageOverageService.send_overage_notification(user, 'grace_period_start')
            logger.info(f"Grace period started for user {user.username}")
            
        elif storage.is_in_grace_period and timezone.now() > storage.grace_period_end:
            # Grace period has ended
            storage.end_grace_period()
            StorageOverageService.send_overage_notification(user, 'grace_period_end')
            logger.info(f"Grace period ended for user {user.username}")
            
        return True
    
    @staticmethod
    def send_overage_notification(user, notification_type):
        """Send email notification about storage overage"""
        try:
            storage = UserStorage.objects.get(user=user)
        except UserStorage.DoesNotExist:
            return False
        
        # Determine email template and subject based on notification type
        templates = {
            'grace_period_start': {
                'subject': 'Speicher überschritten - 30 Tage Kulanzzeit gestartet',
                'template': 'videos/emails/grace_period_start.html'
            },
            'grace_period_warning': {
                'subject': 'Speicher überschritten - Kulanzzeit läuft bald ab',
                'template': 'videos/emails/grace_period_warning.html'
            },
            'grace_period_end': {
                'subject': 'Kulanzzeit abgelaufen - Funktionen eingeschränkt',
                'template': 'videos/emails/grace_period_end.html'
            },
            'restriction_escalation': {
                'subject': 'Weitere Funktionen eingeschränkt - Speicher freigeben',
                'template': 'videos/emails/restriction_escalation.html'
            }
        }
        
        if notification_type not in templates:
            logger.error(f"Unknown notification type: {notification_type}")
            return False
        
        template_info = templates[notification_type]
        
        # Prepare email context
        context = {
            'user': user,
            'storage': storage,
            'overage_mb': storage.get_overage_amount_mb(),
            'used_mb': storage.get_used_storage_mb(),
            'max_mb': storage.get_max_storage_mb(),
            'grace_period_end': storage.grace_period_end,
            'restriction_message': storage.get_restriction_message(),
        }
        
        try:
            # Render email content
            html_message = render_to_string(template_info['template'], context)
            
            # Send email
            send_mail(
                subject=template_info['subject'],
                message='',  # Plain text version (could be added later)
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            # Update notification tracking
            storage.storage_overage_notified = True
            storage.last_overage_notification = timezone.now()
            storage.save()
            
            logger.info(f"Overage notification sent to {user.email} - Type: {notification_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send overage notification to {user.email}: {str(e)}")
            return False
    
    @staticmethod
    def check_all_users_storage():
        """Check storage overage for all users - for scheduled task"""
        logger.info("Starting storage overage check for all users")
        
        overaged_users = 0
        notifications_sent = 0
        
        for storage in UserStorage.objects.select_related('user').all():
            user = storage.user
            
            # Check for overage
            if StorageOverageService.check_user_storage_overage(user):
                overaged_users += 1
                
                # Send warning notification 3 days before grace period ends
                if (storage.is_in_grace_period and 
                    storage.grace_period_end and 
                    timezone.now() > storage.grace_period_end - timedelta(days=3) and
                    (not storage.last_overage_notification or 
                     storage.last_overage_notification < storage.grace_period_end - timedelta(days=3))):
                    
                    StorageOverageService.send_overage_notification(user, 'grace_period_warning')
                    notifications_sent += 1
        
        logger.info(f"Storage check completed. Overaged users: {overaged_users}, Notifications sent: {notifications_sent}")
        return overaged_users, notifications_sent
    
    @staticmethod
    def escalate_restrictions_for_overaged_users():
        """Escalate restrictions for users who remain overaged after grace period"""
        logger.info("Escalating restrictions for overaged users")
        
        escalated_users = 0
        
        # Find users with active restrictions who are still overaged
        for storage in UserStorage.objects.filter(
            overage_restriction_level__gt=0,
            overage_restriction_level__lt=3
        ).select_related('user'):
            
            if storage.is_storage_exceeded():
                # Escalate restrictions every 30 days
                if (storage.last_overage_notification and 
                    timezone.now() > storage.last_overage_notification + timedelta(days=30)):
                    
                    storage.escalate_restrictions()
                    StorageOverageService.send_overage_notification(storage.user, 'restriction_escalation')
                    escalated_users += 1
        
        logger.info(f"Restrictions escalated for {escalated_users} users")
        return escalated_users


class VideoArchivingService:
    """Service for managing video archiving when storage is exceeded"""
    
    @staticmethod
    def archive_videos_for_user(user, target_reduction_mb):
        """Archive videos for a user to reduce storage by target amount"""
        from .models import Video, UserStorage
        
        try:
            storage = UserStorage.objects.get(user=user)
        except UserStorage.DoesNotExist:
            return False, "User storage not found"
        
        # Get active videos ordered by archival score (highest first = most likely to archive)
        active_videos = Video.objects.filter(
            user=user,
            status='active'
        ).order_by('-created_at')  # Start with oldest videos
        
        if not active_videos.exists():
            return False, "No active videos to archive"
        
        # Calculate archival scores and sort
        videos_with_scores = []
        for video in active_videos:
            score = video.get_archival_score()
            videos_with_scores.append((video, score))
        
        # Sort by score (highest score = first to archive)
        videos_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        target_bytes = target_reduction_mb * 1024 * 1024
        archived_bytes = 0
        archived_videos = []
        
        for video, score in videos_with_scores:
            if archived_bytes >= target_bytes:
                break
                
            # Skip high-priority videos unless absolutely necessary
            if video.priority >= 4 and archived_bytes > target_bytes * 0.8:
                continue
            
            video.archive(reason="Automatic archiving due to storage overage")
            archived_bytes += video.file_size
            archived_videos.append(video)
            
            logger.info(f"Archived video: {video.title} ({video.file_size / (1024*1024):.1f} MB) for user {user.username}")
        
        # Update user storage
        storage.used_storage -= archived_bytes
        storage.save()
        
        # Send notification about archived videos
        if archived_videos:
            VideoArchivingService.send_archiving_notification(user, archived_videos, archived_bytes)
        
        return True, f"Archived {len(archived_videos)} videos, freed {archived_bytes / (1024*1024):.1f} MB"
    
    @staticmethod
    def send_archiving_notification(user, archived_videos, freed_bytes):
        """Send notification about archived videos"""
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        
        context = {
            'user': user,
            'archived_videos': archived_videos,
            'freed_mb': freed_bytes / (1024 * 1024),
            'archive_count': len(archived_videos),
        }
        
        try:
            html_message = render_to_string('videos/emails/videos_archived.html', context)
            
            send_mail(
                subject=f'{len(archived_videos)} Videos archiviert - Speicherplatz freigegeben',
                message='',
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            logger.info(f"Archiving notification sent to {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to send archiving notification to {user.email}: {str(e)}")
    
    @staticmethod
    def restore_user_videos(user):
        """Restore all archived videos for a user (when they upgrade)"""
        from .models import Video, UserStorage
        
        archived_videos = Video.objects.filter(user=user, status='archived')
        restored_count = 0
        restored_bytes = 0
        
        for video in archived_videos:
            video.restore()
            restored_count += 1
            restored_bytes += video.file_size
            logger.info(f"Restored video: {video.title} for user {user.username}")
        
        # Update user storage
        try:
            storage = UserStorage.objects.get(user=user)
            storage.used_storage += restored_bytes
            storage.save()
        except UserStorage.DoesNotExist:
            pass
        
        return restored_count, restored_bytes
    
    @staticmethod
    def cleanup_expired_archives():
        """Delete videos that have been archived for more than 90 days"""
        from .models import Video
        from django.utils import timezone
        
        expired_videos = Video.objects.filter(
            status='archived',
            archive_expires_at__lt=timezone.now()
        )
        
        deleted_count = 0
        for video in expired_videos:
            try:
                # Delete the actual file
                if video.video_file:
                    video.video_file.delete()
                if video.thumbnail:
                    video.thumbnail.delete()
                
                # Delete the database record
                video.delete()
                deleted_count += 1
                logger.info(f"Permanently deleted expired archived video: {video.title}")
                
            except Exception as e:
                logger.error(f"Failed to delete expired video {video.id}: {str(e)}")
        
        return deleted_count
    
    @staticmethod
    def get_archivable_videos_for_user(user, target_mb=None):
        """Get list of videos that would be archived for a user"""
        from .models import Video
        
        active_videos = Video.objects.filter(user=user, status='active')
        
        videos_with_scores = []
        for video in active_videos:
            score = video.get_archival_score()
            videos_with_scores.append({
                'video': video,
                'score': score,
                'size_mb': video.file_size / (1024 * 1024),
                'age_days': (timezone.now() - video.created_at).days,
                'priority_name': dict(Video.PRIORITY_CHOICES)[video.priority]
            })
        
        # Sort by archival score (highest first)
        videos_with_scores.sort(key=lambda x: x['score'], reverse=True)
        
        if target_mb:
            # Return only videos needed to reach target
            selected_videos = []
            total_mb = 0
            for item in videos_with_scores:
                if total_mb >= target_mb:
                    break
                selected_videos.append(item)
                total_mb += item['size_mb']
            return selected_videos
        
        return videos_with_scores