"""
Import exactly 500 emails with proper pagination
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount
from mail_app.services import EmailSyncService


class Command(BaseCommand):
    help = 'Import exactly 500 emails with proper pagination'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"📧 Importing 500 emails for: {account.email_address}")
        
        # Get inbox folder
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("No inbox folder found"))
            return
        
        # Check current count
        current_count = inbox.emails.count()
        self.stdout.write(f"📊 Current emails in inbox: {current_count}")
        
        sync_service = EmailSyncService(account)
        
        # Sync exactly 500 emails - the pagination should handle this automatically
        try:
            self.stdout.write("🔄 Starting sync with limit=500...")
            stats = sync_service.sync_emails(folder=inbox, limit=500)
            
            self.stdout.write(f"\n📊 Sync results:")
            self.stdout.write(f"  • Fetched from API: {stats['fetched']}")
            self.stdout.write(f"  • Created in DB: {stats['created']}")
            self.stdout.write(f"  • Updated in DB: {stats['updated']}")
            self.stdout.write(f"  • Errors: {stats['errors']}")
            
            # Check final count
            final_count = inbox.emails.count()
            self.stdout.write(f"\n📬 Final emails in inbox: {final_count}")
            
            if stats['fetched'] >= 500:
                self.stdout.write(self.style.SUCCESS("✅ SUCCESS: API returned 500+ emails"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ API only returned {stats['fetched']} emails"))
            
            if final_count >= 500:
                self.stdout.write(self.style.SUCCESS("✅ SUCCESS: 500+ emails now in database"))
            elif final_count >= 400:
                self.stdout.write(self.style.SUCCESS(f"✅ GOOD: {final_count} emails in database (close to 500)"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ Only {final_count} emails in database"))
            
            # Show some sample emails to verify they exist
            self.stdout.write(f"\n📧 Sample emails:")
            sample_emails = inbox.emails.order_by('-sent_at')[:5]
            for email in sample_emails:
                self.stdout.write(f"  - ID:{email.id} - {email.subject[:60]}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Sync failed: {e}"))