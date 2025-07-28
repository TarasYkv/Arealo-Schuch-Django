"""
Import 500 emails to test if all sync correctly without errors
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount
from mail_app.services import EmailSyncService


class Command(BaseCommand):
    help = 'Import 500 emails to test if all sync correctly without errors'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"📧 Testing import of 500 emails for: {account.email_address}")
        
        # Get inbox folder
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("No inbox folder found"))
            return
        
        sync_service = EmailSyncService(account)
        
        # Sync 500 emails
        try:
            stats = sync_service.sync_emails(folder=inbox, limit=500)
            
            self.stdout.write(f"\n📊 Sync results:")
            self.stdout.write(f"  • Fetched: {stats['fetched']}")
            self.stdout.write(f"  • Created: {stats['created']}")
            self.stdout.write(f"  • Updated: {stats['updated']}")
            self.stdout.write(f"  • Errors: {stats['errors']}")
            
            success_rate = (stats['created'] / stats['fetched'] * 100) if stats['fetched'] > 0 else 0
            self.stdout.write(f"  • Success rate: {success_rate:.1f}%")
            
            if stats['errors'] == 0:
                self.stdout.write(self.style.SUCCESS("✅ Perfect! No errors - all emails processed successfully."))
            elif stats['errors'] < 10:
                self.stdout.write(self.style.WARNING(f"⚠️ Minor issues: {stats['errors']} errors, but mostly successful."))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Significant issues: {stats['errors']} errors."))
                
            # Check final counts
            final_count = inbox.emails.count()
            self.stdout.write(f"\n📬 Total emails in inbox: {final_count}")
            
            # Check if we got the expected 500 new emails
            if stats['created'] == 500:
                self.stdout.write(self.style.SUCCESS("🎯 Perfect! Got exactly 500 new emails as requested."))
            elif stats['created'] >= 400:
                self.stdout.write(self.style.SUCCESS(f"✅ Good! Got {stats['created']} emails (close to 500 target)."))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ Got only {stats['created']} emails instead of 500."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Sync failed: {e}"))