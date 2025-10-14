# streamrec/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class RecordingSession(models.Model):
    """
    Model to track user recording sessions for analytics and optimization
    """
    QUALITY_CHOICES = [
        ('low', 'Niedrig'),
        ('medium', 'Mittel'),
        ('high', 'Hoch'),
    ]
    
    STATUS_CHOICES = [
        ('started', 'Gestartet'),
        ('recording', 'Aufnahme'),
        ('paused', 'Pausiert'),
        ('completed', 'Abgeschlossen'),
        ('failed', 'Fehlgeschlagen'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recording_sessions')
    
    # Session info
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='started')
    
    # Technical details
    streams_used = models.JSONField(default=list)  # ['camera', 'screen']
    layout_used = models.CharField(max_length=100, blank=True)
    video_quality = models.CharField(max_length=10, choices=QUALITY_CHOICES, default='medium')
    audio_quality = models.CharField(max_length=10, choices=QUALITY_CHOICES, default='medium')
    
    # Recording metrics
    duration_seconds = models.PositiveIntegerField(default=0)
    file_size_mb = models.FloatField(null=True, blank=True)
    format_used = models.CharField(max_length=10, default='webm')
    
    # Performance metrics
    browser_info = models.CharField(max_length=100, blank=True)
    performance_issues = models.JSONField(default=list)
    
    # User experience
    user_rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-5 stars
    feedback = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Aufnahme-Session'
        verbose_name_plural = 'Aufnahme-Sessions'
        indexes = [
            models.Index(fields=['user', '-started_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Recording {self.id} - {self.user.username} ({self.started_at.strftime('%Y-%m-%d %H:%M')})"

    @property
    def duration_formatted(self):
        """Return duration in MM:SS format"""
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def is_active(self):
        """Check if session is still active"""
        return self.status in ['started', 'recording', 'paused']

    def mark_completed(self, duration_seconds, file_size_mb=None):
        """Mark session as completed with final metrics"""
        self.status = 'completed'
        self.ended_at = timezone.now()
        self.duration_seconds = duration_seconds
        if file_size_mb:
            self.file_size_mb = file_size_mb
        self.save()

    def mark_failed(self, error_message=''):
        """Mark session as failed"""
        self.status = 'failed'
        self.ended_at = timezone.now()
        if error_message:
            self.performance_issues.append({
                'timestamp': timezone.now().isoformat(),
                'error': error_message
            })
        self.save()


class UserPreferences(models.Model):
    """
    User preferences for StreamRec application
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streamrec_preferences')
    
    # Default quality settings
    default_video_quality = models.CharField(
        max_length=10, 
        choices=RecordingSession.QUALITY_CHOICES, 
        default='medium'
    )
    default_audio_quality = models.CharField(
        max_length=10, 
        choices=RecordingSession.QUALITY_CHOICES, 
        default='medium'
    )
    
    # Preferred layout
    preferred_layout = models.CharField(max_length=100, default='pip-top-right')
    
    # UI preferences
    show_notifications = models.BooleanField(default=True)
    auto_save_settings = models.BooleanField(default=True)
    
    # Advanced settings
    auto_start_composition = models.BooleanField(default=True)
    include_system_audio = models.BooleanField(default=True)
    preferred_format = models.CharField(max_length=10, default='webm')
    
    # Privacy settings
    analytics_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Benutzer-Einstellungen'
        verbose_name_plural = 'Benutzer-Einstellungen'

    def __str__(self):
        return f"StreamRec Preferences - {self.user.username}"


class StreamRecAnalytics(models.Model):
    """
    Analytics data for StreamRec usage patterns and performance
    """
    date = models.DateField(default=timezone.now)
    
    # Usage metrics
    total_sessions = models.PositiveIntegerField(default=0)
    successful_sessions = models.PositiveIntegerField(default=0)
    failed_sessions = models.PositiveIntegerField(default=0)
    
    # Content metrics
    camera_usage = models.PositiveIntegerField(default=0)
    screen_usage = models.PositiveIntegerField(default=0)
    multi_stream_usage = models.PositiveIntegerField(default=0)
    
    # Performance metrics
    avg_duration_seconds = models.FloatField(default=0)
    avg_file_size_mb = models.FloatField(default=0)
    most_used_layout = models.CharField(max_length=100, blank=True)
    
    # Browser analytics
    browser_stats = models.JSONField(default=dict)  # {'Chrome': 45, 'Firefox': 23, ...}
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Analytics Daten'
        verbose_name_plural = 'Analytics Daten'
        unique_together = ['date']

    def __str__(self):
        return f"StreamRec Analytics - {self.date}"
