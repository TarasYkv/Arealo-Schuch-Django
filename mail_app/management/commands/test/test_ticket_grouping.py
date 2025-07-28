"""
Management command to test the new ticket grouping functionality.
"""
from django.core.management.base import BaseCommand
from mail_app.models import Email, Ticket, EmailAccount
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test the new ticket grouping functionality'

    def handle(self, *args, **options):
        self.stdout.write("🧪 Testing ticket grouping functionality...")
        
        # Get active account
        try:
            account = EmailAccount.objects.filter(is_active=True).first()
            if not account:
                self.stdout.write(self.style.ERROR("❌ No active email account found"))
                return
                
            self.stdout.write(f"📧 Using account: {account.email_address}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error getting account: {str(e)}"))
            return
        
        # Test subject normalization
        self.stdout.write("\n🔍 Testing subject normalization:")
        test_subjects = [
            "Important Meeting",
            "Re: Important Meeting", 
            "RE: Important Meeting",
            "Fw: Important Meeting",
            "AW: Important Meeting",
            "Re: Re: Important Meeting",
            "[URGENT] Important Meeting",
            "Antwort: Important Meeting",
        ]
        
        normalized_subjects = {}
        for subject in test_subjects:
            normalized = Ticket.normalize_subject(subject)
            normalized_subjects[subject] = normalized
            self.stdout.write(f"  '{subject}' → '{normalized}'")
        
        # Check if similar subjects are normalized to the same value
        unique_normalized = set(normalized_subjects.values())
        self.stdout.write(f"  📊 {len(test_subjects)} subjects → {len(unique_normalized)} unique normalized")
        
        if len(unique_normalized) == 1:
            self.stdout.write(self.style.SUCCESS("  ✅ All subjects normalized to same value"))
        else:
            self.stdout.write(self.style.WARNING(f"  ⚠️  Multiple normalized values: {unique_normalized}"))
        
        # Test email grouping
        self.stdout.write("\n📨 Testing email grouping...")
        
        # Find some test emails
        test_emails = Email.objects.filter(account=account)[:5]
        if not test_emails.exists():
            self.stdout.write(self.style.WARNING("⚠️  No emails found for testing"))
            return
        
        self.stdout.write(f"Found {test_emails.count()} emails for testing")
        
        # Test grouping by email address
        self.stdout.write("\n🔗 Testing grouping by email address:")
        for email in test_emails:
            # Reset email state
            email.is_open = True  # Mark as open FIRST
            email.ticket = None
            email.save()
            
            # Test creating ticket
            ticket = Ticket.create_or_update_for_email(
                email=email,
                grouping_mode='email',
                auto_group_related=True
            )
            
            if ticket:
                grouped_count = ticket.emails.filter(is_open=True).count()
                self.stdout.write(f"  📧 Email {email.id} from {email.from_email}")
                self.stdout.write(f"     → Ticket {ticket.id}, grouped {grouped_count} emails")
            else:
                self.stdout.write(f"  ❌ Failed to create ticket for email {email.id}")
        
        # Test grouping by email + subject
        self.stdout.write("\n🔗 Testing grouping by email + subject:")
        
        # Reset all emails safely
        Email.objects.filter(account=account).update(is_open=False, ticket=None)
        # Delete tickets after clearing references
        Ticket.objects.filter(account=account).delete()
        
        for email in test_emails:
            # Mark email as open first
            email.is_open = True
            email.save()
            
            # Test creating ticket with subject grouping
            ticket = Ticket.create_or_update_for_email(
                email=email,
                grouping_mode='email_subject',
                auto_group_related=True
            )
            
            if ticket:
                grouped_count = ticket.emails.filter(is_open=True).count()
                self.stdout.write(f"  📧 Email {email.id} from {email.from_email}")
                self.stdout.write(f"     Subject: '{email.subject}'")
                self.stdout.write(f"     Normalized: '{ticket.normalized_subject}'")
                self.stdout.write(f"     → Ticket {ticket.id}, grouped {grouped_count} emails")
            else:
                self.stdout.write(f"  ❌ Failed to create ticket for email {email.id}")
        
        # Summary
        self.stdout.write("\n📊 Summary:")
        total_tickets = Ticket.objects.filter(account=account).count()
        total_open_emails = Email.objects.filter(account=account, is_open=True).count()
        
        self.stdout.write(f"  🎫 Total tickets created: {total_tickets}")
        self.stdout.write(f"  📧 Total open emails: {total_open_emails}")
        
        # Show ticket details
        for ticket in Ticket.objects.filter(account=account):
            emails_in_ticket = ticket.emails.filter(is_open=True).count()
            self.stdout.write(f"  🎫 Ticket {ticket.id}: {ticket.sender_email} ({ticket.grouping_mode}) - {emails_in_ticket} emails")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Ticket grouping test completed!"))