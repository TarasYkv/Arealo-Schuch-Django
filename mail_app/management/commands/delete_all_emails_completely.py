"""
Delete ALL emails from ALL folders completely and verify deletion
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount, Email


class Command(BaseCommand):
    help = 'Delete ALL emails from ALL folders completely and verify deletion'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"🗑️ Completely deleting ALL emails for account: {account.email_address}")
        
        # Count before deletion
        total_before = account.emails.count()
        self.stdout.write(f"📧 Emails before deletion: {total_before}")
        
        if total_before == 0:
            self.stdout.write(self.style.SUCCESS("✅ No emails to delete"))
            return
        
        # Delete ALL emails using different methods
        self.stdout.write("🗑️ Method 1: Delete via account relationship...")
        deleted_1, _ = account.emails.all().delete()
        
        remaining_1 = account.emails.count()
        self.stdout.write(f"Deleted: {deleted_1}, Remaining: {remaining_1}")
        
        if remaining_1 > 0:
            self.stdout.write("🗑️ Method 2: Delete via Email model directly...")
            deleted_2, _ = Email.objects.filter(account=account).delete()
            self.stdout.write(f"Deleted: {deleted_2}")
        
        # Final check
        final_count = account.emails.count()
        total_deleted = total_before - final_count
        
        if final_count == 0:
            self.stdout.write(self.style.SUCCESS(f"✅ SUCCESS: All {total_deleted} emails deleted"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ FAILED: {final_count} emails remain"))
        
        # Update folder counts
        self.stdout.write("📊 Updating folder counts...")
        for folder in account.folders.all():
            folder.update_counts()
            self.stdout.write(f"  {folder.name}: {folder.total_count} total, {folder.unread_count} unread")
        
        self.stdout.write(f"\n📋 Final summary:")
        self.stdout.write(f"  Emails before: {total_before}")
        self.stdout.write(f"  Emails after: {final_count}")
        self.stdout.write(f"  Total deleted: {total_deleted}")