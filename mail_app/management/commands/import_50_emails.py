"""
Import only 50 emails to test if threading errors are fixed
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount
from mail_app.services import EmailSyncService


class Command(BaseCommand):
    help = 'Import 50 emails to test if threading errors are fixed'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"📧 Testing import of 50 emails for: {account.email_address}")
        
        # Get inbox folder
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("No inbox folder found"))
            return
        
        sync_service = EmailSyncService(account)
        
        # Sync only 50 emails to test
        try:
            stats = sync_service.sync_emails(folder=inbox, limit=50)
            
            self.stdout.write(f"\n📊 Sync results:")
            self.stdout.write(f"  • Fetched: {stats['fetched']}")
            self.stdout.write(f"  • Created: {stats['created']}")
            self.stdout.write(f"  • Updated: {stats['updated']}")
            self.stdout.write(f"  • Errors: {stats['errors']}")
            
            if stats['errors'] == 0:
                self.stdout.write(self.style.SUCCESS("✅ No errors! Threading issue fixed."))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Still {stats['errors']} errors. Threading issue not fully fixed."))
                
            # Check final counts
            final_count = inbox.emails.count()
            self.stdout.write(f"\n📬 Total emails in inbox: {final_count}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Sync failed: {e}"))