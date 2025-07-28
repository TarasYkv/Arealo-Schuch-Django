"""
Email and Thread Models
"""
from django.db import models
from django.contrib.auth import get_user_model
import re
from ..constants import EMAIL_STATUS_CHOICES

User = get_user_model()


class EmailThread(models.Model):
    """
    Model representing an email conversation/thread.
    """
    account = models.ForeignKey('mail_app.EmailAccount', on_delete=models.CASCADE, related_name='threads')
    subject = models.CharField(max_length=998)
    thread_id = models.CharField(max_length=255, unique=True)
    
    # Thread metadata
    participants = models.JSONField(default=list)  # List of email addresses
    message_count = models.IntegerField(default=0)
    unread_count = models.IntegerField(default=0)
    
    # Timestamps
    first_message_at = models.DateTimeField()
    last_message_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email Thread"
        verbose_name_plural = "Email Threads"
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['account', '-last_message_at']),
            models.Index(fields=['thread_id']),
        ]
    
    def __str__(self):
        return f"Thread: {self.subject[:50]} ({self.message_count} messages)"
    
    def update_thread_stats(self):
        """Update thread statistics based on associated emails."""
        emails = self.emails.all()
        
        if emails.exists():
            self.message_count = emails.count()
            self.unread_count = emails.filter(is_read=False).count()
            self.first_message_at = emails.order_by('sent_at').first().sent_at
            self.last_message_at = emails.order_by('-sent_at').first().sent_at
            
            # Update participants list
            participants = set()
            for email in emails:
                participants.add(email.from_email)
                participants.update(email.to_emails)
                participants.update(email.cc_emails)
            
            # Remove empty emails and account email
            participants.discard('')
            participants.discard(self.account.email_address)
            self.participants = list(participants)
            
            self.save()


class Email(models.Model):
    """
    Model representing an email message.
    """
    MESSAGE_TYPES = [
        ('received', 'Received'),
        ('sent', 'Sent'),
        ('draft', 'Draft'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
    ]
    
    # Basic email information
    account = models.ForeignKey('mail_app.EmailAccount', on_delete=models.CASCADE, related_name='emails')
    folder = models.ForeignKey('mail_app.Folder', on_delete=models.CASCADE, related_name='emails')
    thread = models.ForeignKey(EmailThread, on_delete=models.CASCADE, related_name='emails', null=True, blank=True)
    
    # Email identifiers
    zoho_message_id = models.CharField(max_length=255, unique=True)
    message_id = models.CharField(max_length=255, blank=True)  # RFC 2822 Message-ID
    zoho_thread_id = models.CharField(max_length=255, blank=True)  # Zoho's thread ID
    
    # Email headers
    subject = models.CharField(max_length=998, blank=True)  # RFC 2822 limit
    from_email = models.EmailField()
    from_name = models.CharField(max_length=255, blank=True)
    to_emails = models.JSONField(default=list)  # List of recipient emails
    cc_emails = models.JSONField(default=list)  # CC recipients
    bcc_emails = models.JSONField(default=list)  # BCC recipients
    reply_to = models.EmailField(blank=True)
    
    # Email content
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    
    # Email metadata
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='received')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    
    # Email status
    is_read = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    
    # Ticket system fields
    is_open = models.BooleanField(default=False, help_text="Email is marked as open/requires action")
    ticket = models.ForeignKey('mail_app.Ticket', on_delete=models.SET_NULL, null=True, blank=True, related_name='emails')
    
    # Timestamps
    sent_at = models.DateTimeField()
    received_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email"
        verbose_name_plural = "Emails"
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['account', 'folder', '-sent_at']),
            models.Index(fields=['zoho_message_id']),
            models.Index(fields=['is_read', 'is_starred']),
            models.Index(fields=['zoho_thread_id']),
        ]
    
    def __str__(self):
        return f"{self.subject[:50]} - {self.from_email}"
    
    @property
    def has_attachments(self):
        return self.attachments.exists()
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read', 'updated_at'])
            # Update folder counts
            if hasattr(self.folder, 'update_counts'):
                self.folder.update_counts()
    
    def mark_as_unread(self):
        if self.is_read:
            self.is_read = False
            self.save(update_fields=['is_read', 'updated_at'])
            # Update folder counts
            if hasattr(self.folder, 'update_counts'):
                self.folder.update_counts()
    
    @property
    def body_preview(self):
        """Return a clean preview of the email body for display."""
        if self.body_text:
            # Remove extra whitespace and newlines
            clean_text = re.sub(r'\s+', ' ', self.body_text.strip())
            return clean_text[:200] + '...' if len(clean_text) > 200 else clean_text
        elif self.body_html:
            # Strip HTML tags for preview
            import html
            from django.utils.html import strip_tags
            clean_html = html.unescape(strip_tags(self.body_html))
            clean_text = re.sub(r'\s+', ' ', clean_html.strip())
            return clean_text[:200] + '...' if len(clean_text) > 200 else clean_text
        return "Keine Vorschau verfügbar"
    
    @property
    def status_display(self):
        """Get human-readable status"""
        if self.is_spam:
            return "Spam"
        if not self.is_read:
            return "Ungelesen"
        if self.is_starred:
            return "Markiert"
        if self.is_important:
            return "Wichtig"
        return "Gelesen"
    
    def get_participants_display(self):
        """Get formatted list of email participants"""
        participants = []
        if self.from_email and self.from_email != self.account.email_address:
            participants.append(self.from_email)
        participants.extend([email for email in self.to_emails if email != self.account.email_address])
        participants.extend([email for email in self.cc_emails if email != self.account.email_address])
        return list(set(participants))  # Remove duplicates


class EmailAttachment(models.Model):
    """
    Model representing email attachments.
    """
    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name='attachments')
    
    # File information
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    file_size = models.PositiveIntegerField()  # Size in bytes
    
    # Zoho-specific identifiers
    zoho_attachment_id = models.CharField(max_length=255, blank=True)
    
    # File storage (optional - for caching)
    file_data = models.BinaryField(blank=True, null=True)
    is_cached = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'mail_app_attachment'
        verbose_name = "Email Attachment"
        verbose_name_plural = "Email Attachments"
        ordering = ['filename']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['zoho_attachment_id']),
        ]
    
    def __str__(self):
        return f"{self.filename} ({self.email.subject[:30]})"
    
    @property
    def file_size_human(self):
        """Return file size in human readable format."""
        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    @property
    def is_image(self):
        """Check if attachment is an image"""
        return self.content_type.startswith('image/')
    
    @property
    def is_document(self):
        """Check if attachment is a document"""
        document_types = [
            'application/pdf',
            'application/msword', 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain'
        ]
        return self.content_type in document_types