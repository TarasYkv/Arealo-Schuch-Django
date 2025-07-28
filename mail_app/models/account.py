"""
Email Account Models
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedTextField

User = get_user_model()


class EmailAccount(models.Model):
    """
    Model representing an email account configuration for Zoho Mail integration.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_accounts')
    email_address = models.EmailField(unique=True)
    display_name = models.CharField(max_length=255, blank=True)
    
    # OAuth2 Credentials (encrypted)
    access_token = EncryptedTextField(blank=True, null=True)
    refresh_token = EncryptedTextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    
    # Account settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    sync_enabled = models.BooleanField(default=True)
    last_sync = models.DateTimeField(blank=True, null=True)
    
    # Email signature
    signature = models.TextField(blank=True)
    
    # Zoho-specific fields
    zoho_account_id = models.CharField(max_length=50, blank=True, verbose_name='Zoho Account ID')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email Account"
        verbose_name_plural = "Email Accounts"
        ordering = ['-is_default', 'email_address']
    
    def __str__(self):
        return f"{self.email_address} ({self.user.username})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default account per user
        if self.is_default:
            EmailAccount.objects.filter(
                user=self.user, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def needs_reauth(self):
        """Check if account needs re-authentication"""
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at
    
    @property
    def sync_status(self):
        """Get latest sync status"""
        latest_sync = self.sync_logs.order_by('-started_at').first()
        return latest_sync.status if latest_sync else 'never'
    
    def get_folder_by_type(self, folder_type):
        """Get folder by type (inbox, sent, etc.)"""
        return self.folders.filter(folder_type=folder_type).first()
    
    def get_unread_count(self):
        """Get total unread email count"""
        return self.emails.filter(is_read=False).count()
    
    def get_total_email_count(self):
        """Get total email count"""
        return self.emails.count()