"""
Delete ALL emails from ALL folders
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount, Email


class Command(BaseCommand):
    help = 'Delete ALL emails from ALL folders'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"🗑️ Deleting ALL emails for account: {account.email_address}")
        
        # Count emails per folder before deletion
        folders = account.folders.all()
        total_emails = 0
        
        self.stdout.write(f"\n📊 Emails per folder before deletion:")
        for folder in folders:
            count = folder.emails.count()
            total_emails += count
            if count > 0:
                self.stdout.write(f"  {folder.name}: {count} emails")
        
        self.stdout.write(f"\n📧 Total emails to delete: {total_emails}")
        
        if total_emails == 0:
            self.stdout.write(self.style.SUCCESS("✅ No emails to delete - all folders are already empty"))
            return
        
        # Ask for confirmation if running interactively
        if self.stdout.isatty():
            confirm = input(f"\nDelete all {total_emails} emails? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write("❌ Deletion cancelled")
                return
        
        # Delete ALL emails from ALL folders
        deleted_count, _ = account.emails.all().delete()
        self.stdout.write(f"\n🗑️ Deleted {deleted_count} emails")
        
        # Verify deletion and show folder counts after
        self.stdout.write(f"\n📊 Emails per folder after deletion:")
        total_remaining = 0
        for folder in folders:
            count = folder.emails.count()
            stored_total = folder.total_count
            stored_unread = folder.unread_count
            total_remaining += count
            
            status = "✅" if count == 0 and stored_total == 0 and stored_unread == 0 else "❌"
            self.stdout.write(f"  {status} {folder.name}: {count} actual, {stored_total} stored total, {stored_unread} stored unread")
        
        if total_remaining == 0:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Perfect! All {deleted_count} emails deleted from all folders"))
        else:
            self.stdout.write(self.style.ERROR(f"\n❌ Problem: {total_remaining} emails remain"))
        
        # Show final summary
        self.stdout.write(f"\n📋 Summary:")
        self.stdout.write(f"  Total deleted: {deleted_count}")
        self.stdout.write(f"  Total remaining: {total_remaining}")
        self.stdout.write(f"  Folders checked: {len(folders)}")