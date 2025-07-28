"""
Management command to fix ticket status issues.
"""
from django.core.management.base import BaseCommand
from mail_app.models import Ticket, Email


class Command(BaseCommand):
    help = 'Fix ticket status issues for open emails'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Fixing ticket status issues...")
        
        # Find tickets that should be open but are closed
        closed_tickets_with_open_emails = Ticket.objects.filter(
            status='closed',
            emails__is_open=True
        ).distinct()
        
        fixed_count = 0
        for ticket in closed_tickets_with_open_emails:
            open_email_count = ticket.emails.filter(is_open=True).count()
            if open_email_count > 0:
                self.stdout.write(f"  📌 Reopening ticket {ticket.id} ({ticket.sender_email}) - {open_email_count} open emails")
                ticket.status = 'open'
                ticket.closed_at = None
                ticket.save()
                fixed_count += 1
        
        # Find open emails without tickets
        open_emails_without_tickets = Email.objects.filter(
            is_open=True,
            ticket__isnull=True
        )
        
        created_count = 0
        for email in open_emails_without_tickets:
            self.stdout.write(f"  🎫 Creating ticket for email {email.id} from {email.from_email}")
            ticket = Ticket.create_or_update_for_email(email)
            if ticket:
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Fixed {fixed_count} tickets, created {created_count} new tickets"
            )
        )