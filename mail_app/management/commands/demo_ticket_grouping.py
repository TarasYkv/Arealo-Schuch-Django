"""
Management command to demonstrate the new ticket grouping functionality.
"""
from django.core.management.base import BaseCommand
from mail_app.models import Email, Ticket, EmailAccount
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Demo: Show current ticket grouping functionality'

    def handle(self, *args, **options):
        self.stdout.write("🎫 Current Ticket System Status")
        self.stdout.write("=" * 50)
        
        # Get active account
        try:
            account = EmailAccount.objects.filter(is_active=True).first()
            if not account:
                self.stdout.write(self.style.ERROR("❌ No active email account found"))
                return
                
            self.stdout.write(f"📧 Account: {account.email_address}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error getting account: {str(e)}"))
            return
        
        # Show current tickets
        tickets = Ticket.objects.filter(account=account, status='open')
        self.stdout.write(f"\n🎫 Current Open Tickets: {tickets.count()}")
        
        for ticket in tickets:
            email_count = ticket.emails.filter(is_open=True).count()
            self.stdout.write(f"  🎫 Ticket {ticket.id}:")
            self.stdout.write(f"     📧 Sender: {ticket.sender_email}")
            self.stdout.write(f"     📝 Subject: {ticket.subject_prefix}")
            self.stdout.write(f"     🔗 Mode: {ticket.get_grouping_mode_display()}")
            self.stdout.write(f"     📊 Emails: {email_count}")
            if ticket.normalized_subject:
                self.stdout.write(f"     🔍 Normalized: '{ticket.normalized_subject}'")
            self.stdout.write("")
        
        # Show open emails not in tickets
        open_emails_no_ticket = Email.objects.filter(
            account=account,
            is_open=True,
            ticket__isnull=True
        )
        
        if open_emails_no_ticket.exists():
            self.stdout.write(f"⚠️  Open emails without tickets: {open_emails_no_ticket.count()}")
            for email in open_emails_no_ticket[:3]:
                self.stdout.write(f"  📧 {email.id}: {email.from_email} - {email.subject[:50]}")
        
        # Show subject normalization examples
        self.stdout.write("\n🔍 Subject Normalization Examples:")
        sample_emails = Email.objects.filter(account=account)[:5]
        
        for email in sample_emails:
            normalized = Ticket.normalize_subject(email.subject)
            self.stdout.write(f"  Original: '{email.subject}'")
            self.stdout.write(f"  Normalized: '{normalized}'")
            self.stdout.write("")
        
        self.stdout.write(self.style.SUCCESS("✅ Demo completed!"))