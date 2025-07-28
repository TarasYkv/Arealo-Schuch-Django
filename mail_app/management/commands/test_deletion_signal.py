"""
Test deletion signal to verify folder counts update when emails are deleted
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount, Email


class Command(BaseCommand):
    help = 'Test deletion signal by deleting emails and checking folder count updates'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"Testing deletion signal for account: {account.email_address}")
        
        # Get inbox folder with emails
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("No inbox folder found"))
            return
        
        # Get some emails to delete
        emails_to_delete = inbox.emails.all()[:3]  # Take first 3 emails
        
        if not emails_to_delete:
            self.stdout.write(self.style.WARNING("No emails in inbox to test deletion"))
            return
        
        self.stdout.write(f"\n--- Testing deletion of {len(emails_to_delete)} emails from {inbox.name} ---")
        
        # Show counts before deletion
        old_total = inbox.total_count
        old_unread = inbox.unread_count
        self.stdout.write(f"Before deletion: total={old_total}, unread={old_unread}")
        
        # Delete emails one by one and verify signal works
        for i, email in enumerate(emails_to_delete, 1):
            self.stdout.write(f"\nDeleting email {i}: {email.subject[:50]}")
            was_unread = not email.is_read
            email.delete()
            
            # Refresh folder from database to get updated counts
            inbox.refresh_from_db()
            expected_total = old_total - i
            expected_unread = old_unread - (i if was_unread else 0)
            
            self.stdout.write(f"After deletion {i}: total={inbox.total_count} (expected: {expected_total}), unread={inbox.unread_count}")
            
            if inbox.total_count == expected_total:
                self.stdout.write(self.style.SUCCESS(f"✅ Total count correct after deletion {i}"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Total count incorrect after deletion {i}"))
        
        # Verify final counts
        actual_total = inbox.emails.count()
        actual_unread = inbox.emails.filter(is_read=False).count()
        
        self.stdout.write(f"\n--- Final verification ---")
        self.stdout.write(f"Stored counts: total={inbox.total_count}, unread={inbox.unread_count}")
        self.stdout.write(f"Actual counts: total={actual_total}, unread={actual_unread}")
        
        if inbox.total_count == actual_total and inbox.unread_count == actual_unread:
            self.stdout.write(self.style.SUCCESS("✅ Deletion signal is working correctly! Folder counts are updated automatically."))
        else:
            self.stdout.write(self.style.ERROR("❌ Deletion signal is not working. Folder counts don't match actual counts."))