from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
import uuid
import os
from django.core.validators import FileExtensionValidator
from django.db.models import Sum


def video_upload_path(instance, filename):
    """Generate upload path for videos"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('videos', str(instance.user.id), filename)


def thumbnail_upload_path(instance, filename):
    """Generate upload path for thumbnails"""
    ext = filename.split('.')[-1]
    filename = f"thumb_{uuid.uuid4()}.{ext}"
    return os.path.join('videos', str(instance.user.id), 'thumbnails', filename)


class UserStorage(models.Model):
    """Track storage usage per user"""
    # Storage tier options with prices
    STORAGE_TIERS = {
        50: {'price': 0.00, 'name': 'Kostenlos'},      # 50MB = Free
        1024: {'price': 1.99, 'name': '1GB Plan'},      # 1GB = 1.99€
        2048: {'price': 2.99, 'name': '2GB Plan'},      # 2GB = 2.99€
        5120: {'price': 6.99, 'name': '5GB Plan'},      # 5GB = 6.99€
        10240: {'price': 9.99, 'name': '10GB Plan'},    # 10GB = 9.99€
    }
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    used_storage = models.BigIntegerField(default=0)  # in bytes
    max_storage = models.BigIntegerField(default=52428800)  # 50MB default
    is_premium = models.BooleanField(default=False)
    
    # Grace period management
    grace_period_start = models.DateTimeField(null=True, blank=True)
    grace_period_end = models.DateTimeField(null=True, blank=True)
    is_in_grace_period = models.BooleanField(default=False)
    
    # Storage overage tracking
    storage_overage_notified = models.BooleanField(default=False)
    last_overage_notification = models.DateTimeField(null=True, blank=True)
    overage_restriction_level = models.IntegerField(default=0)  # 0=none, 1=uploads, 2=sharing, 3=archiving
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Benutzer-Speicher'
        verbose_name_plural = 'Benutzer-Speicher'

    def get_used_storage_mb(self):
        return self.used_storage / (1024 * 1024)
    
    def get_max_storage_mb(self):
        return self.max_storage / (1024 * 1024)
    
    def get_max_storage_gb(self):
        return self.max_storage / (1024 * 1024 * 1024)
    
    def has_storage_available(self, file_size):
        return (self.used_storage + file_size) <= self.max_storage
    
    def get_current_tier(self):
        """Get current storage tier in MB"""
        current_mb = self.get_max_storage_mb()
        for tier_mb in sorted(self.STORAGE_TIERS.keys()):
            if current_mb <= tier_mb:
                return tier_mb
        return max(self.STORAGE_TIERS.keys())
    
    def get_current_price(self):
        """Get current monthly price"""
        tier = self.get_current_tier()
        return self.STORAGE_TIERS[tier]['price']
    
    def get_tier_name(self):
        """Get current tier name"""
        tier = self.get_current_tier()
        return self.STORAGE_TIERS[tier]['name']
    
    @classmethod
    def get_price_for_storage_mb(cls, storage_mb):
        """Get price for a specific storage amount in MB"""
        for tier_mb in sorted(cls.STORAGE_TIERS.keys()):
            if storage_mb <= tier_mb:
                return cls.STORAGE_TIERS[tier_mb]['price']
        return cls.STORAGE_TIERS[max(cls.STORAGE_TIERS.keys())]['price']
    
    @classmethod
    def get_storage_options(cls):
        """Get all available storage options for slider"""
        return [
            {
                'mb': tier_mb,
                'gb': tier_mb / 1024 if tier_mb >= 1024 else None,
                'price': data['price'],
                'name': data['name'],
                'bytes': tier_mb * 1024 * 1024
            }
            for tier_mb, data in sorted(cls.STORAGE_TIERS.items())
        ]
    
    def sync_with_stripe_subscription(self):
        """Sync storage limits with user's Stripe subscription"""
        from .subscription_sync import StorageSubscriptionSync
        return StorageSubscriptionSync.sync_user_storage(self.user)
    
    def get_plan_info(self):
        """Get comprehensive plan information including Stripe data"""
        from .subscription_sync import StorageSubscriptionSync
        return StorageSubscriptionSync.get_user_plan_info(self.user)
    
    def is_storage_exceeded(self):
        """Check if user's storage usage exceeds their limit"""
        return self.used_storage > self.max_storage
    
    def get_overage_amount_mb(self):
        """Get the amount of storage overage in MB"""
        if not self.is_storage_exceeded():
            return 0
        return (self.used_storage - self.max_storage) / (1024 * 1024)
    
    def start_grace_period(self):
        """Start the 30-day grace period for storage overage"""
        from django.utils import timezone
        from datetime import timedelta
        
        self.grace_period_start = timezone.now()
        self.grace_period_end = self.grace_period_start + timedelta(days=30)
        self.is_in_grace_period = True
        self.overage_restriction_level = 0
        self.save()
    
    def end_grace_period(self):
        """End the grace period and apply restrictions"""
        self.is_in_grace_period = False
        self.overage_restriction_level = 1  # Start with upload restrictions
        self.save()
    
    def escalate_restrictions(self):
        """Escalate restriction level (uploads -> sharing -> archiving)"""
        if self.overage_restriction_level < 3:
            self.overage_restriction_level += 1
            self.save()
    
    def clear_overage_status(self):
        """Clear overage status when storage is back within limits"""
        self.grace_period_start = None
        self.grace_period_end = None
        self.is_in_grace_period = False
        self.storage_overage_notified = False
        self.last_overage_notification = None
        self.overage_restriction_level = 0
        self.save()
    
    def can_upload(self):
        """Check if user can upload new videos"""
        if not self.is_storage_exceeded():
            return True
        return self.overage_restriction_level == 0  # Only during grace period
    
    def can_share(self):
        """Check if user can share videos"""
        if not self.is_storage_exceeded():
            return True
        return self.overage_restriction_level < 2  # Disabled after level 1
    
    def get_restriction_message(self):
        """Get message explaining current restrictions"""
        if not self.is_storage_exceeded():
            return None
            
        if self.is_in_grace_period:
            return f"Speicher überschritten. Kulanzzeit läuft ab am {self.grace_period_end.strftime('%d.%m.%Y')}."
        
        if self.overage_restriction_level == 1:
            return "Neue Uploads deaktiviert. Bitte Speicherplatz freigeben oder Abo erweitern."
        elif self.overage_restriction_level == 2:
            return "Uploads und Sharing deaktiviert. Bitte Speicherplatz freigeben oder Abo erweitern."
        elif self.overage_restriction_level >= 3:
            return "Archivierung eingeleitet. Videos werden nach Priorität archiviert."
        
        return None


class Video(models.Model):
    """Video model for direct hosting"""
    
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('archived', 'Archiviert'),
        ('deleted', 'Gelöscht'),
    ]
    
    PRIORITY_CHOICES = [
        (1, 'Niedrig'),
        (2, 'Normal'),
        (3, 'Hoch'),
        (4, 'Kritisch'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_file = models.FileField(
        upload_to=video_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm'])]
    )
    thumbnail = models.ImageField(
        upload_to=thumbnail_upload_path,
        blank=True,
        null=True
    )
    
    file_size = models.BigIntegerField(default=0)  # in bytes
    duration = models.IntegerField(default=0, help_text="Duration in seconds")  # Video duration
    
    # Video status and archiving
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)  # User-defined priority
    
    # Archiving metadata
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_reason = models.CharField(max_length=255, blank=True)
    archive_expires_at = models.DateTimeField(null=True, blank=True)  # When archived video gets permanently deleted
    
    # Access tracking for archiving decisions
    last_accessed = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    access_count = models.IntegerField(default=0)
    
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    share_link = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Video'
        verbose_name_plural = 'Videos'
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.share_link:
            self.share_link = f"/v/{self.unique_id}/"
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return self.share_link
    
    def get_embed_url(self):
        return f"/videos/embed/{self.unique_id}/"
    
    def archive(self, reason="Storage overage"):
        """Archive this video"""
        from django.utils import timezone
        from datetime import timedelta
        
        self.status = 'archived'
        self.archived_at = timezone.now()
        self.archived_reason = reason
        self.archive_expires_at = self.archived_at + timedelta(days=90)  # 90 days to restore
        self.save()
    
    def restore(self):
        """Restore archived video"""
        self.status = 'active'
        self.archived_at = None
        self.archived_reason = ''
        self.archive_expires_at = None
        self.save()
    
    def soft_delete(self):
        """Soft delete video (can be restored)"""
        self.status = 'deleted'
        self.save()
    
    def track_access(self):
        """Track video access for archiving decisions"""
        from django.utils import timezone
        self.last_accessed = timezone.now()
        self.access_count += 1
        self.save()
    
    def is_archived(self):
        return self.status == 'archived'
    
    def is_deleted(self):
        return self.status == 'deleted'
    
    def is_active(self):
        return self.status == 'active'
    
    def get_archival_score(self):
        """Calculate archival priority score (lower = more likely to be archived)"""
        from django.utils import timezone
        from datetime import timedelta
        
        score = 0
        
        # Age factor (older videos get higher archival score)
        age_days = (timezone.now() - self.created_at).days
        score += age_days * 0.1
        
        # Size factor (larger videos get higher archival score)
        size_mb = self.file_size / (1024 * 1024)
        score += size_mb * 0.05
        
        # Access factor (less accessed videos get higher archival score)
        days_since_access = (timezone.now() - self.last_accessed).days
        score += days_since_access * 0.2
        
        # Priority factor (lower priority videos get higher archival score)
        priority_multiplier = {1: 2.0, 2: 1.0, 3: 0.5, 4: 0.1}
        score *= priority_multiplier.get(self.priority, 1.0)
        
        # Invert access count (fewer accesses = higher archival score)
        if self.access_count > 0:
            score += 10 / self.access_count
        else:
            score += 10
        
        return score


class Subscription(models.Model):
    """Flexible subscription plans for storage"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    storage_limit_mb = models.IntegerField(default=50)  # Storage in MB (50, 1024, 2048, 5120, 10240)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Abonnement'
        verbose_name_plural = 'Abonnements'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_plan_name()}"
    
    def get_plan_name(self):
        """Get human readable plan name"""
        if self.storage_limit_mb == 50:
            return "Kostenlos"
        elif self.storage_limit_mb >= 1024:
            gb = self.storage_limit_mb / 1024
            return f"{gb:g}GB Plan"
        else:
            return f"{self.storage_limit_mb}MB Plan"
    
    def get_storage_bytes(self):
        """Get storage limit in bytes"""
        return self.storage_limit_mb * 1024 * 1024
    
    def is_free_plan(self):
        """Check if this is the free plan"""
        return self.storage_limit_mb <= 50
    
    def is_premium_plan(self):
        """Check if this is a premium plan"""
        return self.storage_limit_mb > 50
