"""
Sync and Logging Models
"""
from django.db import models
from django.utils import timezone
from ..constants import SYNC_STATUS_CHOICES, SYNC_TYPE_CHOICES


class SyncLog(models.Model):
    """
    Model for logging email synchronization activities.
    """
    account = models.ForeignKey('mail_app.EmailAccount', on_delete=models.CASCADE, related_name='sync_logs')
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPE_CHOICES, default='manual')
    status = models.CharField(max_length=20, choices=SYNC_STATUS_CHOICES, default='pending')
    
    # Sync statistics
    emails_fetched = models.IntegerField(default=0)
    emails_created = models.IntegerField(default=0)
    emails_updated = models.IntegerField(default=0)
    folders_synced = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    # Sync details
    error_message = models.TextField(blank=True)
    sync_duration = models.DurationField(blank=True, null=True)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['account', '-started_at']),
            models.Index(fields=['status']),
            models.Index(fields=['sync_type']),
        ]
    
    def __str__(self):
        return f"{self.account.email_address} - {self.sync_type} ({self.status})"
    
    @property
    def duration_display(self):
        """Get human-readable duration"""
        if self.sync_duration:
            total_seconds = int(self.sync_duration.total_seconds())
            minutes, seconds = divmod(total_seconds, 60)
            if minutes > 0:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"
        return "N/A"
    
    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.emails_fetched > 0:
            success_count = self.emails_created + self.emails_updated
            return (success_count / self.emails_fetched) * 100
        return 0
    
    def mark_completed(self, success=True):
        """Mark sync as completed"""
        self.completed_at = timezone.now()
        self.status = 'completed' if success else 'failed'
        if self.started_at and self.completed_at:
            self.sync_duration = self.completed_at - self.started_at
        self.save(update_fields=['completed_at', 'status', 'sync_duration'])
    
    def add_error(self, error_message):
        """Add error to sync log"""
        self.error_count += 1
        if self.error_message:
            self.error_message += f"\n{error_message}"
        else:
            self.error_message = error_message
        self.save(update_fields=['error_count', 'error_message'])
    
    def get_stats_summary(self):
        """Get summary of sync statistics"""
        return {
            'fetched': self.emails_fetched,
            'created': self.emails_created,
            'updated': self.emails_updated,
            'errors': self.error_count,
            'duration': self.duration_display,
            'success_rate': f"{self.success_rate:.1f}%"
        }