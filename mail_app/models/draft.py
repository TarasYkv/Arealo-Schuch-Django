"""
Email Draft Models
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailDraft(models.Model):
    """
    Model for storing email drafts before sending.
    """
    account = models.ForeignKey('mail_app.EmailAccount', on_delete=models.CASCADE, related_name='drafts')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Draft content
    subject = models.CharField(max_length=998, blank=True)
    to_emails = models.JSONField(default=list)
    cc_emails = models.JSONField(default=list)
    bcc_emails = models.JSONField(default=list)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    
    # Reply/Forward context
    in_reply_to = models.ForeignKey('mail_app.Email', on_delete=models.SET_NULL, null=True, blank=True)
    is_forward = models.BooleanField(default=False)
    
    # Draft metadata
    is_auto_saved = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email Draft"
        verbose_name_plural = "Email Drafts"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['account', 'user', '-updated_at']),
            models.Index(fields=['in_reply_to']),
        ]
    
    def __str__(self):
        return f"Draft: {self.subject[:50]} ({self.user.username})"
    
    @property
    def recipients_count(self):
        """Get total number of recipients"""
        return len(self.to_emails) + len(self.cc_emails) + len(self.bcc_emails)
    
    @property
    def has_content(self):
        """Check if draft has any content"""
        return bool(self.subject.strip() or self.body_text.strip() or self.body_html.strip())
    
    def get_reply_context(self):
        """Get context information for reply/forward"""
        if self.in_reply_to:
            return {
                'original_subject': self.in_reply_to.subject,
                'original_sender': self.in_reply_to.from_email,
                'original_date': self.in_reply_to.sent_at,
                'is_forward': self.is_forward
            }
        return None