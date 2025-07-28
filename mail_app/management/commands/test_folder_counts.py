"""
Test command to verify folder count updates when emails are deleted
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount, Email, Folder


class Command(BaseCommand):
    help = 'Test folder count updates when emails are deleted'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"Testing folder counts for account: {account.email_address}")
        
        # Get folders and show current counts
        folders = account.folders.all()
        if not folders:
            self.stdout.write(self.style.ERROR("No folders found"))
            return
        
        self.stdout.write("\n--- Current folder counts ---")
        for folder in folders:
            email_count = folder.emails.count()
            unread_count = folder.emails.filter(is_read=False).count()
            self.stdout.write(f"{folder.name}: {folder.total_count} stored / {email_count} actual | {folder.unread_count} unread stored / {unread_count} actual unread")
        
        # Test deletion
        test_folder = folders.first()
        emails_to_delete = test_folder.emails.all()[:2]  # Take first 2 emails
        
        if not emails_to_delete:
            self.stdout.write(self.style.WARNING(f"No emails in folder {test_folder.name} to test deletion"))
            return
        
        self.stdout.write(f"\n--- Testing deletion of {len(emails_to_delete)} emails from {test_folder.name} ---")
        
        # Show counts before deletion
        old_total = test_folder.total_count
        old_unread = test_folder.unread_count
        self.stdout.write(f"Before deletion: total={old_total}, unread={old_unread}")
        
        # Delete emails one by one to test signal
        for email in emails_to_delete:
            self.stdout.write(f"Deleting email: {email.subject[:50]}")
            was_unread = not email.is_read
            email.delete()
            
            # Refresh folder from database
            test_folder.refresh_from_db()
            self.stdout.write(f"After deletion: total={test_folder.total_count}, unread={test_folder.unread_count}")
        
        # Verify final counts
        actual_total = test_folder.emails.count()
        actual_unread = test_folder.emails.filter(is_read=False).count()
        
        self.stdout.write(f"\n--- Final verification ---")
        self.stdout.write(f"Stored counts: total={test_folder.total_count}, unread={test_folder.unread_count}")
        self.stdout.write(f"Actual counts: total={actual_total}, unread={actual_unread}")
        
        if test_folder.total_count == actual_total and test_folder.unread_count == actual_unread:
            self.stdout.write(self.style.SUCCESS("✅ Folder counts are correct after deletion!"))
        else:
            self.stdout.write(self.style.ERROR("❌ Folder counts don't match actual counts"))
        
        # Update all folder counts to fix any discrepancies
        self.stdout.write("\n--- Updating all folder counts ---")
        for folder in folders:
            old_total = folder.total_count
            old_unread = folder.unread_count
            folder.update_counts()
            self.stdout.write(f"{folder.name}: {old_total} -> {folder.total_count} total, {old_unread} -> {folder.unread_count} unread")