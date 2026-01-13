from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class StorageLog(models.Model):
    """
    Logs aller Storage-Aktivitäten für Analytics
    Trackt Uploads/Downloads über alle Apps hinweg
    """

    ACTION_CHOICES = [
        ('upload', 'Upload'),
        ('delete', 'Löschen'),
        ('archive', 'Archivieren'),
        ('restore', 'Wiederherstellen'),
    ]

    APP_CHOICES = [
        ('videos', 'Videos'),
        ('fileshare', 'FileShare'),
        ('streamrec', 'StreamRec'),
        ('shopify', 'Shopify Manager'),
        ('image_editor', 'Bild Editor'),
        ('organization', 'Organization'),
        ('chat', 'Chat'),
        ('android_apk_manager', 'Android APK Manager'),
        ('other', 'Andere'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='storage_logs',
        verbose_name='Benutzer'
    )
    app_name = models.CharField(
        max_length=50,
        choices=APP_CHOICES,
        verbose_name='App',
        db_index=True
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='Aktion',
        db_index=True
    )
    size_bytes = models.BigIntegerField(
        verbose_name='Größe (Bytes)'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadaten',
        help_text='Zusätzliche Informationen (z.B. Dateiname, Typ, etc.)'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erstellt am',
        db_index=True
    )

    class Meta:
        verbose_name = 'Storage-Log'
        verbose_name_plural = 'Storage-Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'app_name', '-created_at']),
            models.Index(fields=['user', 'action', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.get_size_mb():.2f}MB - {self.app_name}"

    def get_size_mb(self):
        """Gibt Größe in MB zurück"""
        return self.size_bytes / (1024 * 1024)

    def get_size_kb(self):
        """Gibt Größe in KB zurück"""
        return self.size_bytes / 1024

    @classmethod
    def get_user_stats(cls, user, days=30):
        """
        Gibt Statistiken für einen User zurück

        Args:
            user: User object
            days: Anzahl Tage zurück (Standard: 30)

        Returns:
            dict mit Stats
        """
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum, Count

        start_date = timezone.now() - timedelta(days=days)

        stats = cls.objects.filter(
            user=user,
            created_at__gte=start_date
        ).aggregate(
            total_uploads=Count('id', filter=models.Q(action='upload')),
            total_deletions=Count('id', filter=models.Q(action='delete')),
            total_uploaded_bytes=Sum('size_bytes', filter=models.Q(action='upload')),
            total_deleted_bytes=Sum('size_bytes', filter=models.Q(action='delete')),
        )

        # Per-App Statistiken
        per_app = cls.objects.filter(
            user=user,
            created_at__gte=start_date
        ).values('app_name').annotate(
            uploads=Count('id', filter=models.Q(action='upload')),
            total_size=Sum('size_bytes', filter=models.Q(action='upload'))
        ).order_by('-total_size')

        return {
            'period_days': days,
            'total_uploads': stats['total_uploads'] or 0,
            'total_deletions': stats['total_deletions'] or 0,
            'total_uploaded_mb': (stats['total_uploaded_bytes'] or 0) / (1024 * 1024),
            'total_deleted_mb': (stats['total_deleted_bytes'] or 0) / (1024 * 1024),
            'per_app': list(per_app),
        }
