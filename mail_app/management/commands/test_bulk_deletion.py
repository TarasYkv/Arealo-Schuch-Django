"""
Test bulk deletion to verify folder counts reset when all emails are deleted
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount


class Command(BaseCommand):
    help = 'Test bulk deletion by deleting all emails and checking folder count resets'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"Testing bulk deletion for account: {account.email_address}")
        
        # Get inbox folder
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("No inbox folder found"))
            return
        
        # Show counts before deletion
        old_total = inbox.total_count
        old_unread = inbox.unread_count
        actual_count = inbox.emails.count()
        
        self.stdout.write(f"\n--- Before bulk deletion ---")
        self.stdout.write(f"Stored counts: total={old_total}, unread={old_unread}")
        self.stdout.write(f"Actual count: {actual_count}")
        
        if actual_count == 0:
            self.stdout.write(self.style.WARNING("No emails to delete"))
            return
        
        # Perform bulk deletion (similar to what user reported)
        self.stdout.write(f"\n--- Deleting all {actual_count} emails ---")
        deleted_count, _ = inbox.emails.all().delete()
        self.stdout.write(f"Deleted {deleted_count} emails")
        
        # Check folder counts after deletion
        inbox.refresh_from_db()
        new_total = inbox.total_count
        new_unread = inbox.unread_count
        remaining_count = inbox.emails.count()
        
        self.stdout.write(f"\n--- After bulk deletion ---")
        self.stdout.write(f"Stored counts: total={new_total}, unread={new_unread}")
        self.stdout.write(f"Actual count: {remaining_count}")
        
        # Verify the fix worked
        if new_total == 0 and new_unread == 0 and remaining_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Bulk deletion works correctly! Folder counts are reset to 0."))
        else:
            self.stdout.write(self.style.ERROR("❌ Bulk deletion issue still exists. Folder counts are not properly reset."))
            
            # Manual fix if needed
            if remaining_count == 0 and (new_total > 0 or new_unread > 0):
                self.stdout.write("Manually updating folder counts...")
                inbox.update_counts()
                self.stdout.write(f"After manual update: total={inbox.total_count}, unread={inbox.unread_count}")
        
        # Test with other folders too
        self.stdout.write(f"\n--- Checking all folders ---")
        for folder in account.folders.all():
            stored_total = folder.total_count
            stored_unread = folder.unread_count
            actual_total = folder.emails.count()
            actual_unread = folder.emails.filter(is_read=False).count()
            
            status = "✅" if stored_total == actual_total and stored_unread == actual_unread else "❌"
            self.stdout.write(f"{status} {folder.name}: {stored_total}/{actual_total} total, {stored_unread}/{actual_unread} unread")