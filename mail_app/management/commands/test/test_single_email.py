"""
Test creating a ticket for a specific email.
"""
from django.core.management.base import BaseCommand
from mail_app.models import Email, Ticket, EmailAccount
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test creating a ticket for a specific email'

    def add_arguments(self, parser):
        parser.add_argument('email_id', type=int, help='Email ID to test')
        parser.add_argument(
            '--grouping-mode',
            choices=['email', 'email_subject'],
            default='email',
            help='Grouping mode to test'
        )

    def handle(self, *args, **options):
        email_id = options['email_id']
        grouping_mode = options['grouping_mode']
        
        try:
            email = Email.objects.get(id=email_id)
            self.stdout.write(f"📧 Testing Email {email.id}:")
            self.stdout.write(f"   From: {email.from_email}")
            self.stdout.write(f"   Subject: {email.subject}")
            self.stdout.write(f"   Is open: {email.is_open}")
            self.stdout.write(f"   Current ticket: {email.ticket.id if email.ticket else 'None'}")
            
            # Test creating a ticket
            self.stdout.write(f"\n🎫 Creating ticket with mode: {grouping_mode}")
            
            if not email.is_open:
                self.stdout.write("   Marking email as open first...")
                email.is_open = True
                email.save()
            
            ticket = Ticket.create_or_update_for_email(
                email, 
                grouping_mode=grouping_mode, 
                auto_group_related=True
            )
            
            if ticket:
                grouped_emails = ticket.emails.filter(is_open=True).count()
                all_related = ticket.emails.filter(is_open=True)
                
                self.stdout.write(f"   ✅ Ticket created: {ticket.id}")
                self.stdout.write(f"   📊 Total emails in ticket: {grouped_emails}")
                self.stdout.write(f"   🔗 Grouping mode: {ticket.get_grouping_mode_display()}")
                self.stdout.write(f"   🏷️  Subject prefix: {ticket.subject_prefix}")
                
                if ticket.normalized_subject:
                    self.stdout.write(f"   🔍 Normalized subject: '{ticket.normalized_subject}'")
                
                self.stdout.write(f"\n📧 Emails in this ticket:")
                for related_email in all_related:
                    marker = "🎯" if related_email.id == email_id else "📧"
                    self.stdout.write(f"   {marker} {related_email.id}: {related_email.subject[:60]}")
                
                # Check if there are similar emails that weren't grouped
                similar_emails = Email.objects.filter(
                    account=email.account,
                    from_email=email.from_email
                ).exclude(
                    id__in=[e.id for e in all_related]
                )
                
                if similar_emails.exists():
                    self.stdout.write(f"\n📝 Other emails from same sender (not grouped):")
                    for similar in similar_emails[:3]:
                        self.stdout.write(f"   📧 {similar.id}: {similar.subject[:60]} (open: {similar.is_open})")
                
            else:
                self.stdout.write("   ❌ Failed to create ticket")
            
        except Email.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Email {email_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))