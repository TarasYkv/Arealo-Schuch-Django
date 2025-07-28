"""
Folder Models
"""
from django.db import models
from ..constants import FOLDER_TYPES


class Folder(models.Model):
    """
    Model representing email folders (Inbox, Sent, Drafts, etc.)
    """
    account = models.ForeignKey('mail_app.EmailAccount', on_delete=models.CASCADE, related_name='folders')
    name = models.CharField(max_length=255)
    folder_type = models.CharField(max_length=20, choices=FOLDER_TYPES, default='custom')
    zoho_folder_id = models.CharField(max_length=255, blank=True)
    
    # Folder properties
    unread_count = models.IntegerField(default=0)
    total_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Folder"
        verbose_name_plural = "Folders"
        unique_together = ['account', 'zoho_folder_id']
        ordering = ['account', 'folder_type', 'name']
    
    def __str__(self):
        return f"{self.account.email_address} - {self.name}"
    
    def update_counts(self):
        """Update folder email counts"""
        emails = self.emails.all()
        self.total_count = emails.count()
        self.unread_count = emails.filter(is_read=False).count()
        self.save(update_fields=['total_count', 'unread_count'])
    
    @property
    def has_unread(self):
        """Check if folder has unread emails"""
        return self.unread_count > 0
    
    @property
    def icon(self):
        """Get folder icon"""
        from ..constants import FOLDER_ICONS
        return FOLDER_ICONS.get(self.folder_type, '📁')