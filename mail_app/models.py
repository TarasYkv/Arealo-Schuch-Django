from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedTextField
import json
import re

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


class Folder(models.Model):
    """
    Model representing email folders (Inbox, Sent, Drafts, etc.)
    """
    FOLDER_TYPES = [
        ('inbox', 'Inbox'),
        ('sent', 'Sent'),
        ('drafts', 'Drafts'),
        ('trash', 'Trash'),
        ('spam', 'Spam'),
        ('custom', 'Custom'),
    ]
    
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='folders')
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


class EmailThread(models.Model):
    """
    Model representing an email conversation/thread.
    """
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='threads')
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
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='emails')
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='emails')
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
    ticket = models.ForeignKey('Ticket', on_delete=models.SET_NULL, null=True, blank=True, related_name='emails')
    
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
    
    def mark_as_unread(self):
        if self.is_read:
            self.is_read = False
            self.save(update_fields=['is_read', 'updated_at'])
    
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


class Attachment(models.Model):
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
        verbose_name = "Attachment"
        verbose_name_plural = "Attachments"
        ordering = ['filename']
    
    def __str__(self):
        return f"{self.filename} ({self.email.subject[:30]})"
    
    @property
    def file_size_human(self):
        """Return file size in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"


class EmailDraft(models.Model):
    """
    Model for storing email drafts before sending.
    """
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='drafts')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Draft content
    subject = models.CharField(max_length=998, blank=True)
    to_emails = models.JSONField(default=list)
    cc_emails = models.JSONField(default=list)
    bcc_emails = models.JSONField(default=list)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    
    # Reply/Forward context
    in_reply_to = models.ForeignKey(Email, on_delete=models.SET_NULL, null=True, blank=True)
    is_forward = models.BooleanField(default=False)
    
    # Draft metadata
    is_auto_saved = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email Draft"
        verbose_name_plural = "Email Drafts"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Draft: {self.subject[:50]} ({self.user.username})"


class SyncLog(models.Model):
    """
    Model for logging email synchronization activities.
    """
    SYNC_TYPES = [
        ('full', 'Full Sync'),
        ('incremental', 'Incremental Sync'),
        ('manual', 'Manual Sync'),
    ]
    
    STATUS_CHOICES = [
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ]
    
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='sync_logs')
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES, default='incremental')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='started')
    
    # Sync statistics
    emails_fetched = models.IntegerField(default=0)
    emails_created = models.IntegerField(default=0)
    emails_updated = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    
    # Sync details
    error_message = models.TextField(blank=True)
    sync_duration = models.DurationField(blank=True, null=True)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.account.email_address} - {self.sync_type} ({self.status})"


class Ticket(models.Model):
    """
    Model representing a ticket created from open emails.
    Emails can be grouped by sender or by sender+subject.
    """
    STATUS_CHOICES = [
        ('open', 'Offen'),
        ('closed', 'Geschlossen'),
    ]
    
    GROUPING_CHOICES = [
        ('email', 'Nach Email-Adresse'),
        ('email_subject', 'Nach Email + Betreff'),
    ]
    
    # Ticket identification
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='tickets')
    sender_email = models.EmailField(help_text="Email address of the sender")
    sender_name = models.CharField(max_length=255, blank=True, help_text="Display name of the sender")
    
    # Ticket content
    subject_prefix = models.CharField(max_length=200, help_text="Common subject prefix for this ticket")
    normalized_subject = models.CharField(max_length=200, blank=True, help_text="Normalized subject for matching")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    grouping_mode = models.CharField(max_length=20, choices=GROUPING_CHOICES, default='email', 
                                   help_text="How emails are grouped in this ticket")
    
    # Ticket metadata
    email_count = models.PositiveIntegerField(default=0, help_text="Number of emails in this ticket")
    first_email_at = models.DateTimeField(help_text="Timestamp of the first email")
    last_email_at = models.DateTimeField(help_text="Timestamp of the most recent email")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ['-last_email_at']
        unique_together = ['account', 'sender_email', 'normalized_subject', 'grouping_mode']  
        indexes = [
            models.Index(fields=['account', 'status', '-last_email_at']),
            models.Index(fields=['sender_email']),
            models.Index(fields=['normalized_subject']),
            models.Index(fields=['grouping_mode']),
        ]
    
    def __str__(self):
        return f"Ticket: {self.sender_email} - {self.subject_prefix}"
    
    @staticmethod
    def normalize_subject(subject):
        """
        Normalize email subject for intelligent matching.
        Removes prefixes like Re:, Fw:, AW:, etc. and extra whitespace.
        """
        if not subject:
            return ""
        
        import re
        
        # Remove common email prefixes (case insensitive)
        prefixes = [
            r'^re:\s*',           # Re:
            r'^fw:\s*',           # Fw:
            r'^fwd:\s*',          # Fwd:
            r'^aw:\s*',           # AW: (German)
            r'^wg:\s*',           # WG: (German)
            r'^reply:\s*',        # Reply:
            r'^antwort:\s*',      # Antwort: (German)  
            r'^\[.*?\]\s*',       # [Tag] prefixes
            r'^antw:\s*',         # Antw: (German)
        ]
        
        normalized = subject.strip()
        
        # Remove prefixes iteratively (in case of multiple Re: Re: etc.)
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                new_normalized = re.sub(prefix, '', normalized, flags=re.IGNORECASE).strip()
                if new_normalized != normalized:
                    normalized = new_normalized
                    changed = True
        
        # Remove extra whitespace and convert to lowercase for matching
        normalized = re.sub(r'\s+', ' ', normalized).strip().lower()
        
        return normalized
    
    @classmethod
    def find_matching_ticket(cls, account, sender_email, subject, grouping_mode='email', include_closed=False):
        """
        Find an existing ticket that matches the criteria.
        """
        base_query = cls.objects.filter(
            account=account,
            sender_email=sender_email,
            grouping_mode=grouping_mode
        )
        
        if not include_closed:
            base_query = base_query.filter(status='open')
        
        if grouping_mode == 'email':
            # Group only by email address
            return base_query.first()
        elif grouping_mode == 'email_subject':
            # Group by email address and normalized subject
            normalized_subject = cls.normalize_subject(subject)
            if not normalized_subject:
                # If subject is empty, fall back to email-only grouping
                return base_query.filter(normalized_subject='').first()
            
            # Try to find ticket with same normalized subject
            ticket = base_query.filter(normalized_subject=normalized_subject).first()
            return ticket
        
        return None
    
    def update_ticket_stats(self):
        """Update ticket statistics based on associated emails."""
        open_emails = self.emails.filter(is_open=True)
        
        if open_emails.exists():
            self.email_count = open_emails.count()
            self.first_email_at = open_emails.order_by('sent_at').first().sent_at
            self.last_email_at = open_emails.order_by('-sent_at').first().sent_at
            
            # Update subject prefix from most common subject
            subjects = open_emails.values_list('subject', flat=True)
            if subjects:
                # Find common subject prefix
                common_prefix = self._find_common_subject_prefix(subjects)
                if common_prefix:
                    self.subject_prefix = common_prefix
                else:
                    self.subject_prefix = subjects[0][:100]  # Fallback to first subject
            
            self.save()
        else:
            # No open emails left, close ticket
            self.close_ticket()
    
    def _find_common_subject_prefix(self, subjects):
        """Find common prefix in email subjects, removing Re: and Fwd: prefixes."""
        if not subjects:
            return ""
        
        # Clean subjects by removing Re:, Fwd:, etc.
        cleaned_subjects = []
        for subject in subjects:
            cleaned = re.sub(r'^(Re|Fwd|Fw|Aw):\s*', '', subject, flags=re.IGNORECASE).strip()
            if cleaned:
                cleaned_subjects.append(cleaned)
        
        if not cleaned_subjects:
            return ""
        
        # Find longest common prefix
        common_prefix = cleaned_subjects[0]
        for subject in cleaned_subjects[1:]:
            # Find common prefix between current common and this subject
            i = 0
            while i < len(common_prefix) and i < len(subject) and common_prefix[i] == subject[i]:
                i += 1
            common_prefix = common_prefix[:i]
        
        return common_prefix.strip()[:100]  # Limit length
    
    def close_ticket(self):
        """Close the ticket and mark all associated emails as not open."""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save()
        
        # Mark all emails as not open
        self.emails.update(is_open=False, ticket=None)
    
    @classmethod
    def create_or_update_for_email(cls, email, grouping_mode='email', auto_group_related=True):
        """
        Create or update a ticket for the given email and optionally group related emails.
        
        Args:
            email: The email to create a ticket for
            grouping_mode: 'email' or 'email_subject' 
            auto_group_related: If True, automatically add related emails to the ticket
        
        Returns:
            The ticket instance.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"create_or_update_for_email called for email {email.id}, is_open={email.is_open}, grouping_mode={grouping_mode}")
        
        if not email.is_open:
            logger.warning(f"Email {email.id} is not open, returning None")
            return None
        
        logger.info(f"Creating/updating ticket for {email.from_email} from account {email.account.email_address}")
        
        # Find existing matching ticket (both open and closed)
        existing_ticket = cls.find_matching_ticket(
            account=email.account,
            sender_email=email.from_email,
            subject=email.subject,
            grouping_mode=grouping_mode
        )
        
        # If no open ticket found, check for closed tickets that can be reopened
        if not existing_ticket:
            closed_ticket = cls.find_matching_ticket(
                account=email.account,
                sender_email=email.from_email,
                subject=email.subject,
                grouping_mode=grouping_mode,
                include_closed=True
            )
            if closed_ticket:
                existing_ticket = closed_ticket
        
        if existing_ticket:
            logger.info(f"Found existing ticket {existing_ticket.id}")
            ticket = existing_ticket
            
            # If ticket was closed, reopen it
            if ticket.status == 'closed':
                logger.info(f"Reopening closed ticket {ticket.id}")
                ticket.status = 'open'
                ticket.closed_at = None
                ticket.save(update_fields=['status', 'closed_at'])
        else:
            # Create new ticket
            normalized_subject = cls.normalize_subject(email.subject) if grouping_mode == 'email_subject' else ''
            
            ticket = cls.objects.create(
                account=email.account,
                sender_email=email.from_email,
                sender_name=email.from_name,
                subject_prefix=email.subject[:100] if email.subject else '(Kein Betreff)',
                normalized_subject=normalized_subject,
                grouping_mode=grouping_mode,
                first_email_at=email.sent_at,
                last_email_at=email.sent_at,
                email_count=1,
                status='open'
            )
            logger.info(f"Created new ticket {ticket.id}")
        
        # Associate email with ticket
        email.ticket = ticket
        email.save(update_fields=['ticket'])
        
        # Auto-group related emails if requested
        if auto_group_related:
            cls._auto_group_related_emails(ticket, email, grouping_mode)
        
        # Update ticket statistics
        ticket.update_ticket_stats()
        
        return ticket
    
    @classmethod
    def _auto_group_related_emails(cls, ticket, trigger_email, grouping_mode):
        """
        Automatically group related emails into the same ticket.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Auto-grouping related emails for ticket {ticket.id} with mode {grouping_mode}")
        
        # Find related emails that should be in this ticket
        related_emails_query = trigger_email.account.emails.filter(
            from_email=ticket.sender_email
        ).exclude(
            id=trigger_email.id  # Exclude the trigger email itself
        )
        
        if grouping_mode == 'email_subject' and ticket.normalized_subject:
            # Also filter by normalized subject
            related_emails = []
            for email in related_emails_query:
                if cls.normalize_subject(email.subject) == ticket.normalized_subject:
                    related_emails.append(email)
        else:
            # Group all emails from this sender
            related_emails = list(related_emails_query)
        
        # Mark related emails as open and associate with ticket
        updated_count = 0
        for email in related_emails:
            if not email.is_open:
                email.is_open = True
                updated_count += 1
            
            if email.ticket != ticket:
                email.ticket = ticket
            
            email.save(update_fields=['is_open', 'ticket'])
        
        logger.info(f"Auto-grouped {len(related_emails)} related emails, {updated_count} were newly marked as open")
        
        return len(related_emails)