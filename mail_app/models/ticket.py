"""
Ticket System Models
"""
from django.db import models
from django.utils import timezone
import re
from ..constants import TICKET_STATUS_CHOICES, EMAIL_GROUPING_MODES


class Ticket(models.Model):
    """
    Model representing a ticket created from open emails.
    Emails can be grouped by sender or by sender+subject.
    """
    # Ticket identification
    account = models.ForeignKey('mail_app.EmailAccount', on_delete=models.CASCADE, related_name='tickets')
    sender_email = models.EmailField(help_text="Email address of the sender")
    sender_name = models.CharField(max_length=255, blank=True, help_text="Display name of the sender")
    
    # Ticket content
    subject_prefix = models.CharField(max_length=200, help_text="Common subject prefix for this ticket")
    normalized_subject = models.CharField(max_length=200, blank=True, help_text="Normalized subject for matching")
    status = models.CharField(max_length=20, choices=TICKET_STATUS_CHOICES, default='open')
    grouping_mode = models.CharField(max_length=20, choices=EMAIL_GROUPING_MODES, default='subject', 
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
    def find_matching_ticket(cls, account, sender_email, subject, grouping_mode='subject', include_closed=False):
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
        
        if grouping_mode == 'sender':
            # Group only by email address
            return base_query.first()
        elif grouping_mode == 'subject':
            # Group by email address and normalized subject
            normalized_subject = cls.normalize_subject(subject)
            if not normalized_subject:
                # If subject is empty, fall back to sender-only grouping
                return base_query.filter(normalized_subject='').first()
            
            # Try to find ticket with same normalized subject
            ticket = base_query.filter(normalized_subject=normalized_subject).first()
            return ticket
        
        return None
    
    @classmethod
    def create_from_email(cls, email, grouping_mode='subject'):
        """
        Create a new ticket from an email.
        """
        normalized_subject = cls.normalize_subject(email.subject) if grouping_mode == 'subject' else ''
        
        ticket = cls.objects.create(
            account=email.account,
            sender_email=email.from_email,
            sender_name=email.from_name,
            subject_prefix=email.subject[:200],
            normalized_subject=normalized_subject,
            grouping_mode=grouping_mode,
            email_count=1,
            first_email_at=email.sent_at,
            last_email_at=email.sent_at
        )
        
        # Associate email with ticket
        email.ticket = ticket
        email.save(update_fields=['ticket'])
        
        return ticket
    
    def add_email(self, email):
        """
        Add an email to this ticket.
        """
        email.ticket = self
        email.save(update_fields=['ticket'])
        
        # Update ticket statistics
        self.email_count = self.emails.count()
        self.last_email_at = self.emails.order_by('-sent_at').first().sent_at
        self.save(update_fields=['email_count', 'last_email_at', 'updated_at'])
    
    def close_ticket(self):
        """
        Close the ticket and mark all associated emails as closed.
        """
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save(update_fields=['status', 'closed_at', 'updated_at'])
        
        # Mark all emails as closed (not open)
        self.emails.update(is_open=False)
    
    def reopen_ticket(self):
        """
        Reopen a closed ticket.
        """
        self.status = 'open'
        self.closed_at = None
        self.save(update_fields=['status', 'closed_at', 'updated_at'])
        
        # Mark all emails as open again
        self.emails.update(is_open=True)
    
    @property
    def duration_open(self):
        """Get how long the ticket has been open"""
        end_time = self.closed_at if self.closed_at else timezone.now()
        return end_time - self.created_at
    
    @property
    def latest_email(self):
        """Get the most recent email in this ticket"""
        return self.emails.order_by('-sent_at').first()
    
    @property
    def unread_count(self):
        """Get count of unread emails in this ticket"""
        return self.emails.filter(is_read=False).count()
    
    def get_participants(self):
        """Get all unique participants in this ticket"""
        participants = set([self.sender_email])
        for email in self.emails.all():
            participants.update(email.to_emails)
            participants.update(email.cc_emails)
        # Remove account email
        participants.discard(self.account.email_address)
        return list(participants)